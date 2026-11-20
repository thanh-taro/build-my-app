#!/usr/bin/env python3
"""build-my-app web UI server. Standard library only.

  bma_ui.py start [--port N] [--open]   Start in the background and print the URL
  bma_ui.py status                      Print whether it runs, and its URL
  bma_ui.py stop                        Stop it

Serves the room (ui/), a snapshot API, and a server-sent event stream on 127.0.0.1 only.
Every API and stream request needs the random token in the URL that `start` prints.
While it runs, `ui.json` in `.build-my-app/tmp/ui/` tells the hooks to record events;
the server tails that event log and `state.json` and pushes changes to the browser.
Messages typed in the page go to an inbox that the chat bridge (bma_channel.py, an MCP
channel inside the Claude Code session) passes into the session.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import queue
import re
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bma_preview  # noqa: E402
import bma_state  # noqa: E402
from bma_events import append, clip, events_path, lower_first, ui_dir, ui_info_path  # noqa: E402
from bma_resources import memory_state  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
STATIC = PLUGIN_ROOT / "ui"
DEFAULT_PORT = 7311
POLL = 0.4
DONE_KEEP = 40          # finished agents kept for the timeline
STUCK_AFTER = 3         # consecutive failed heavy runs before an agent shows as stuck
QUIET_AFTER = 45        # seconds with no sign of Claude after a web message is delivered
BRIDGE_STALE = 15       # seconds without a heartbeat before a chat bridge counts as gone
MAX_CHAT = 4000         # characters per web message
PREVIEW_EVERY = 5       # seconds between preview liveness checks while a page is open
PREVIEW_IDLE_STOP = 1800  # no page open this long → stop preview servers Claude left running


def project_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def read_info(root: Path) -> dict | None:
    try:
        info = json.loads(ui_info_path(root).read_text())
    except Exception:
        return None
    return info if pid_alive(info.get("pid")) else None


# -- model: events → agents, feed, heavy queue --------------------------------

def short_type(t: str | None) -> str:
    return (t or "general-purpose").split(":")[-1]


class Model:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.agents: dict[str, dict] = {}
        self.pending: list[dict] = []          # Agent tool calls not yet matched to a subagent
        self.feed: deque = deque(maxlen=200)
        self.heavy: dict[str, dict] = {}       # label → {state, code, ts}
        self.assistant = {"now": "", "ts": 0.0}
        self.fresh: list[dict] = []            # feed items not yet pushed to browsers
        self.chats: dict[str, dict] = {}       # web chat_id → its feed item (carries "status")
        self.status_fresh: list[dict] = []     # chat status changes not yet pushed
        self.last_activity = 0.0               # last sign of Claude working (any hook event)
        self.perms: dict[str, dict] = {}       # relayed tool-approval prompts: request_id → card
        self.questions: dict[str, dict] = {}   # AskUserQuestion calls waiting for the page: qid → card
        self.last_interim = ""

    def take_status(self) -> list[dict]:
        with self.lock:
            out, self.status_fresh = self.status_fresh, []
            return out

    def _chat_status(self, chat_id: str, status: str, ts: float) -> None:
        item = self.chats.get(chat_id)
        if item and item.get("status") != status:
            item.update(status=status, status_ts=ts)
            self.status_fresh.append({"chat_id": chat_id, "status": status})

    def check_quiet(self, now: float) -> bool:
        """Flag delivered web messages that got no sign of Claude for a while."""
        changed = False
        with self.lock:
            for cid, item in self.chats.items():
                if item.get("status") == "delivered" and now - item["status_ts"] > QUIET_AFTER:
                    self._chat_status(cid, "quiet", now)
                    self._say("system", "Claude hasn't reacted to your message yet. It may still be busy with a "
                                        "long step. If the terminal never shows your message, restart Claude "
                                        "with channels (see the note under the chat box).", now, kind="note")
                    changed = True
        return changed

    def take_fresh(self) -> list[dict]:
        with self.lock:
            out, self.fresh = self.fresh, []
            return out

    # Each apply returns the kinds of change it made: {"agents", "feed"}.
    def apply(self, e: dict) -> set[str]:
        with self.lock:
            moved_on = (not e.get("agent") and e.get("ev") in ("tool", "spawn", "reply", "prompt")
                        and e.get("tool") != "AskUserQuestion" and self._close_terminal_questions(e.get("ts") or time.time()))
            changed = self._apply(e)
            return (set(changed) | {"questions"}) if moved_on else changed

    def _say(self, who: str, text: str, ts: float, **kw) -> None:
        if text:
            item = {"ts": ts, "who": who, "text": text, **kw}
            self.feed.append(item)
            self.fresh.append(item)

    def _agent(self, aid: str, atype: str | None, ts: float) -> dict:
        a = self.agents.get(aid)
        if a is None:
            a = self.agents[aid] = {"id": aid, "type": short_type(atype), "desc": "", "status": "working",
                                    "now": "", "result": "", "label": None, "fails": 0,
                                    "started": ts, "updated": ts, "ended": None}
        return a

    def _apply(self, e: dict) -> set[str]:
        ev, ts, aid = e.get("ev"), float(e.get("ts") or time.time()), e.get("agent")
        if ev not in ("prompt", "delivered", "heavy_wait", "heavy_run", "heavy_done") and not e.get("interim"):
            self.last_activity = ts
            for cid, item in self.chats.items():  # Claude is active again: it has (or will) read them
                if item.get("status") in ("delivered", "quiet") and item["status_ts"] <= ts:
                    self._chat_status(cid, "seen", ts)
        if ev == "delivered":
            self._chat_status(str(e.get("chat_id")), "delivered", ts)
            return set()
        if ev in ("permission", "permission_answer", "permission_refused", "tool_done"):
            return self._permission(ev, e, ts)
        if ev == "preview":
            self._say("assistant", f"The app is ready to try: {e.get('label') or 'preview'}. Use Open app in the Preview panel.",
                      ts, kind="preview")
            return {"feed", "previews"}
        if ev == "question":
            # "open": the page can answer it; "terminal": shown read-only while it waits in the terminal
            qs = [q for q in (e.get("questions") or []) if isinstance(q, dict) and q.get("question")]
            where = "terminal" if e.get("where") == "terminal" else "open"
            self.questions[str(e.get("qid"))] = {"qid": str(e.get("qid")), "questions": qs, "ts": ts, "state": where,
                                                 "tool_use_id": e.get("tool_use_id"), "main": not aid}
            self.questions = dict(list(self.questions.items())[-20:])
            first = qs[0]["question"] if qs else "a question"
            more = f" (+{len(qs) - 1} more)" if len(qs) > 1 else ""
            self._say("assistant", f"I have a question for you{' in the terminal' if where == 'terminal' else ''}: {first}{more}",
                      ts, kind="question")
            return {"questions", "feed"}
        if ev == "question_done":
            q = self.questions.get(str(e.get("qid")))
            if not q or q["state"] not in ("open", "answering"):   # "answering": the page just sent its reply
                return set()
            if e.get("via") == "terminal":   # still waiting, now in the terminal: keep showing it
                q["state"] = "terminal"
                why = {"terminal": "as you asked", "page closed": "because the page was closed",
                       "timeout": "after waiting 5 minutes"}.get(e.get("reason"), "")
                self._say("system", f"The question moved to the terminal {why}. Answer it there.".replace("  ", " "), ts, kind="note")
            else:
                q["state"] = "done"
            return {"questions", "feed"}
        if ev == "question_answered":
            hit = [q for q in self.questions.values() if q["state"] != "done" and q.get("tool_use_id") == e.get("tool_use_id")]
            for q in hit:
                q["state"] = "done"
            return {"questions"} if hit else set()
        if ev == "spawn" and not aid:
            self.pending.append({"id": e.get("id"), "type": short_type(e.get("spawn_type")),
                                 "desc": e.get("desc") or "", "ts": ts})
            self.pending = self.pending[-20:]
            self.assistant = {"now": e.get("text") or "", "ts": ts}
            return {"agents"}
        if ev == "agent_start" and aid:
            a = self._agent(aid, e.get("type"), ts)
            match = next((p for p in self.pending if p["type"] == a["type"]), None)
            if match:
                self.pending.remove(match)
                a["desc"] = match["desc"]
            a.update(status="working", now=a["desc"] or "Getting started", updated=ts)
            self._say("assistant", f"I've asked {a['type']} to {lower_first(a['desc']) or 'help'}.", ts, kind="spawn", agent=aid)
            return {"agents", "feed"}
        if ev == "spawned":
            child = e.get("child")
            if child and child in self.agents:
                p = next((p for p in self.pending if p["id"] == e.get("id")), None)
                if p:
                    self.pending.remove(p)
                    self.agents[child]["desc"] = self.agents[child]["desc"] or p["desc"]
            return set()
        if ev in ("tool", "spawn") and aid:
            a = self._agent(aid, e.get("type"), ts)
            if a["status"] == "done":
                return set()
            if e.get("label"):
                a["label"] = e["label"]
            a.update(now=e.get("text") or a["now"], updated=ts)
            if a["status"] not in ("queued", "stuck"):  # those change only on heavy-run results
                a["status"] = "working"
            return {"agents"}
        if ev == "tool":
            self.assistant = {"now": e.get("text") or "", "ts": ts}
            return {"agents"}
        if ev == "agent_stop" and aid:
            if aid not in self.agents:  # Claude Code's own helper agents stop without ever starting
                return set()
            a = self._agent(aid, e.get("type"), ts)
            result = clip((e.get("text") or "").split("\n")[0], 200)
            reported = e.get("reported", bool(result))
            oc = e.get("outcome") if e.get("outcome") in ("pass", "fixes", "blocked") else None
            a.update(status="done", result=result, now=result or "Finished", updated=ts, ended=ts,
                     outcome=oc, reported=reported)
            self._say(a["type"], result or "Finished.", ts, kind="done", agent=aid, outcome=oc)
            self._prune()
            return {"agents", "feed"}
        if ev in ("heavy_wait", "heavy_run", "heavy_done"):
            label = e.get("label") or ""
            h = self.heavy.setdefault(label, {"state": "", "code": None, "ts": ts})
            h.update(state={"heavy_wait": "waiting", "heavy_run": "running", "heavy_done": "done"}[ev], ts=ts,
                     code=e.get("code"))
            owner = self._owner(label)
            if owner:
                if ev == "heavy_wait":
                    owner.update(status="queued", now="Waiting for a free heavy-run slot", updated=ts)
                elif ev == "heavy_run":
                    owner.update(status="working", now=f"Running a heavy job for {label}", updated=ts)
                elif e.get("code") not in (0, None):
                    owner["fails"] += 1
                    if owner["fails"] >= STUCK_AFTER:
                        owner.update(status="stuck", now=f"{label} failed {owner['fails']} times in a row", updated=ts)
                        self._say("assistant", f"{owner['type']} is stuck on {label}. I'll get fresh eyes on it.", ts,
                                  kind="stuck", agent=owner["id"])
                        return {"agents", "feed"}
                else:
                    owner.update(fails=0, status="working", updated=ts)
            if ev == "heavy_done":
                self.heavy = {k: v for k, v in self.heavy.items() if v["state"] != "done" or ts - v["ts"] < 120}
            return {"agents"}
        if ev == "prompt" and not aid:
            text, via = e.get("text") or "", e.get("via") or "terminal"
            if via == "web":
                self._say("you", text, ts, via="web", chat_id=e.get("chat_id"), status="sent", status_ts=ts)
                self.chats[str(e.get("chat_id"))] = self.feed[-1]
                self.chats = dict(list(self.chats.items())[-50:])
                return {"feed"}
            # A web message can also reach the prompt hook; don't show it twice.
            if any(i["text"] and i["text"] in text and ts - i["ts"] < 600 for i in self.chats.values()):
                return set()
            self._say("you", text, ts, via=via)
            return {"feed"} | self._close_perms("closed")
        if ev == "reply" and not aid:
            text = e.get("text") or ""
            if e.get("interim"):
                self.last_interim = text
                self._say("assistant", text, ts, kind="note")
                return {"feed"}
            self.assistant = {"now": "", "ts": ts}
            if text.strip() and text.strip() != self.last_interim.strip():
                self._say("assistant", text, ts, kind="reply")
            self.last_interim = ""
            return {"agents", "feed"} | self._close_perms("closed")
        return set()

    def _permission(self, ev: str, e: dict, ts: float) -> set[str]:
        rid = str(e.get("request_id") or "")
        if ev == "permission":
            self.perms[rid] = {"request_id": rid, "tool": e.get("tool") or "", "desc": e.get("desc") or "",
                               "preview": e.get("preview") or "", "hard": bool(e.get("hard")),
                               "reason": e.get("reason"), "bridge": e.get("bridge"), "ts": ts, "state": "open"}
            self.perms = dict(list(self.perms.items())[-30:])
            return {"perms"}
        p = self.perms.get(rid)
        if ev == "permission_answer" and p:
            p["state"] = "allowed" if e.get("behavior") == "allow" else "denied"
            what = p["desc"] or p["tool"]
            self._say("system", f"You {p['state']} from the page: {what}", ts, kind="perm")
            return {"perms", "feed"}
        if ev == "permission_refused" and p:
            p["refused"] = True
            return {"perms"}
        if ev == "tool_done":  # the tool ran, so its prompt was answered in the terminal
            fold = lambda t: re.sub(r"[\s\\\"'`]", "", t or "")
            sig = fold(e.get("sig"))[:60]
            for p in self.perms.values():
                if p["state"] == "open" and p["tool"] == e.get("tool") and sig and sig in fold(p["preview"]):
                    p["state"] = "answered"
                    return {"perms"}
        return set()

    def _close_perms(self, state: str) -> set[str]:
        open_ = [p for p in self.perms.values() if p["state"] == "open"]
        for p in open_:
            p["state"] = state
        return {"perms"} if open_ else set()

    def _close_terminal_questions(self, ts: float) -> bool:
        """The main session did something new, so its question in the terminal is no longer waiting."""
        hit = [q for q in self.questions.values() if q["state"] == "terminal" and q.get("main") and ts > q["ts"] + 0.5]
        for q in hit:
            q["state"] = "done"
        return bool(hit)

    def questions_payload(self) -> list[dict]:
        with self.lock:
            return [dict(q) for q in self.questions.values() if q["state"] in ("open", "terminal")]

    def open_question(self, qid: str) -> dict | None:
        with self.lock:
            q = self.questions.get(qid)
            return dict(q) if q and q["state"] == "open" else None

    def claim(self, qid: str) -> bool:
        """Close a question as the page answers it, so a second answer (another tab, a late click) gets 410."""
        with self.lock:
            q = self.questions.get(qid)
            if not q or q["state"] != "open":
                return False
            q["state"] = "answering"
            return True

    def answered(self, qid: str, answers: dict) -> None:
        """Show the page's answer in the conversation right away."""
        with self.lock:
            text = "\n".join(f"{k} → {v}" for k, v in answers.items()) if len(answers) > 1 else next(iter(answers.values()))
            self._say("you", text, time.time(), via="web")

    def perms_payload(self) -> list[dict]:
        with self.lock:
            return [dict(p) for p in self.perms.values() if p["state"] == "open"]

    def open_perm(self, rid: str) -> dict | None:
        with self.lock:
            p = self.perms.get(rid)
            return dict(p) if p and p["state"] == "open" else None

    def _owner(self, label: str) -> dict | None:
        live = [a for a in self.agents.values() if a["label"] == label and a["status"] != "done"]
        return max(live, key=lambda a: a["updated"]) if live else None

    def _prune(self) -> None:
        done = sorted((a for a in self.agents.values() if a["status"] == "done"), key=lambda a: a["ended"] or 0)
        for a in done[:-DONE_KEEP]:
            del self.agents[a["id"]]

    def agents_payload(self) -> dict:
        with self.lock:
            heavy = {"running": sum(1 for h in self.heavy.values() if h["state"] == "running"),
                     "waiting": sum(1 for h in self.heavy.values() if h["state"] == "waiting")}
            return {"agents": sorted(self.agents.values(), key=lambda a: a["started"]),
                    "assistant": dict(self.assistant), "heavy": heavy}

    def feed_payload(self) -> list:
        with self.lock:
            return list(self.feed)


# -- state snapshot -------------------------------------------------------------

_git_cache = {"at": 0.0, "branch": None}


def git_branch(root: Path) -> str | None:
    if time.time() - _git_cache["at"] > 15:
        try:
            # symbolic-ref also works before the first commit, where rev-parse prints "HEAD"
            r = subprocess.run(["git", "symbolic-ref", "--short", "-q", "HEAD"], cwd=root, capture_output=True,
                               text=True, timeout=3)
            if not r.stdout.strip():
                r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True,
                                   text=True, timeout=3)
            _git_cache["branch"] = r.stdout.strip() or None
        except Exception:
            _git_cache["branch"] = None
        _git_cache["at"] = time.time()
    return _git_cache["branch"]


def state_payload(root: Path) -> dict:
    p = root / ".build-my-app" / "state.json"
    try:
        st = bma_state.migrate(json.loads(p.read_text()))
    except Exception as ex:
        return {"error": f"Cannot read {p}: {ex}"}
    cur = bma_state.current_phase(st)
    phases = [{"id": pid, **{k: st["phases"][pid].get(k) for k in ("title", "status", "step")},
               "gate": st["phases"][pid]["gate"]["status"]} for pid in bma_state.PHASE_IDS]
    return {
        "project": root.name,
        "autonomy": st.get("autonomy"),
        "phases": phases,
        "current": cur,
        "next": [] if cur else bma_state.ready_phases(st),
        "decisions": [{k: d.get(k) for k in ("id", "question", "options", "recommendation", "kind")}
                      for d in st.get("decisions", []) if d.get("status") == "open"],
        "loops": [{"name": k, "round": v.get("round"), "max": v.get("max")}
                  for k, v in st.get("loops", {}).items() if v.get("active")],
        "resources": {**(st.get("resources") or {}), "pressure": memory_state()},
        "environment": st.get("environment") or {},
        "stack": st.get("stack"),
        "design_tool": st.get("design_tool"),
        "branch": git_branch(root),
        "log": st.get("log", [])[-12:],
        "updated": st.get("updated"),
    }


def bridges(root: Path) -> dict:
    """Claude Code sessions with the chat bridge running, and how many can take web messages."""
    out = {"sessions": 0, "chat": 0}
    d = ui_dir(root) / "bridges"
    for f in d.glob("*.json") if d.is_dir() else []:
        try:
            b = json.loads(f.read_text())
        except Exception:
            continue
        if time.time() - b.get("ts", 0) > BRIDGE_STALE or not pid_alive(b.get("pid")):
            f.unlink(missing_ok=True)
            continue
        out["sessions"] += 1
        out["chat"] += 1 if b.get("channel") else 0
    return out


_previews = {"at": 0.0, "items": []}


def previews(root: Path, fresh: bool = False) -> list[dict]:
    """Recorded previews with their state; cached, since checking a simulator takes a moment."""
    if fresh or time.time() - _previews["at"] > PREVIEW_EVERY:
        items = []
        for p in bma_preview.load(root):
            shot = bma_preview.shots_dir(root) / f"{p['id']}.png"
            items.append({k: p.get(k) for k in ("id", "kind", "target", "label", "cmd", "commit", "added")}
                         | {"state": bma_preview.state_of(p), "shot": int(p.get("shot_at") or 0) if shot.exists() else 0})
        _previews.update(at=time.time(), items=items)
    return _previews["items"]


def snapshot(root: Path, model: "Model") -> dict:
    return {"state": state_payload(root), **model.agents_payload(), "feed": model.feed_payload(),
            "bridge": bridges(root), "perms": model.perms_payload(), "questions": model.questions_payload(),
            "previews": previews(root)}


# -- server -------------------------------------------------------------------

class Hub:
    """Fan-out of server-sent events to every open browser tab."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.clients: set[queue.Queue] = set()

    def add(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=500)
        with self.lock:
            self.clients.add(q)
        return q

    def remove(self, q: queue.Queue) -> None:
        with self.lock:
            self.clients.discard(q)

    def send(self, kind: str, data) -> None:
        msg = f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()
        with self.lock:
            for q in list(self.clients):
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    self.clients.discard(q)  # a stuck tab; it reconnects and gets a fresh snapshot


_presence_lock = threading.Lock()


def touch_presence(root: Path, visible: bool) -> None:
    """presence.json: when a page was last open ("seen") and last on screen ("visible")."""
    f = ui_dir(root) / "presence.json"
    with _presence_lock:
        try:
            cur = json.loads(f.read_text())
        except Exception:
            cur = {}
        now = time.time()
        cur.update(seen=now, **({"visible": now} if visible else {}))
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(cur))
        os.replace(tmp, f)


def plugin_version() -> str:
    try:
        return json.loads((Path(__file__).resolve().parents[1] / ".claude-plugin" / "plugin.json").read_text())["version"]
    except Exception:
        return "?"


def watch(root: Path, model: Model, hub: Hub, stop: threading.Event) -> None:
    sp, ep = root / ".build-my-app" / "state.json", events_path(root)
    state_mtime, offset, last_pressure, last_push, last_bridge = 0.0, 0, None, 0.0, None
    last_previews, last_viewer = None, time.time()
    last_seen = 0.0
    while not stop.is_set():
        if hub.clients:
            last_viewer = time.time()
            if last_viewer - last_seen > 10:
                last_seen = last_viewer
                touch_presence(root, visible=False)
            if time.time() - _previews["at"] > PREVIEW_EVERY:
                pv = previews(root, fresh=True)
                if pv != last_previews:
                    last_previews = pv
                    hub.send("previews", pv)
        elif time.time() - last_viewer > PREVIEW_IDLE_STOP:
            last_viewer = time.time()
            stopped = [p["label"] for p in bma_preview.load(root) if bma_preview.stop_owned(root, p)]
            if stopped:
                append(root, {"ev": "reply", "interim": True, "text": "Stopped the idle preview: " + ", ".join(stopped)})
        b = bridges(root)
        if b != last_bridge:
            last_bridge = b
            hub.send("bridge", b)
        if model.check_quiet(time.time()):
            for item in model.take_fresh():
                hub.send("feed", item)
            for st in model.take_status():
                hub.send("chat_status", st)
        try:
            m = sp.stat().st_mtime
            pressure = memory_state() if time.time() - last_push > 10 else last_pressure
            if m != state_mtime or pressure != last_pressure:
                state_mtime, last_pressure, last_push = m, pressure, time.time()
                hub.send("state", state_payload(root))
        except FileNotFoundError:
            pass
        try:
            size = ep.stat().st_size
            if size < offset:
                offset = 0  # rotated
            if size > offset:
                with open(ep, "rb") as f:
                    f.seek(offset)
                    chunk = f.read()
                end = chunk.rfind(b"\n") + 1  # only complete lines
                offset += end
                changed: set[str] = set()
                for line in chunk[:end].splitlines():
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    changed |= model.apply(e)
                for item in model.take_fresh():
                    hub.send("feed", item)
                for st in model.take_status():
                    hub.send("chat_status", st)
                if "agents" in changed:
                    hub.send("agents", model.agents_payload())
                if "previews" in changed:
                    pv = previews(root, fresh=True)
                    last_previews = pv
                    hub.send("previews", pv)
                if "questions" in changed:
                    hub.send("questions", model.questions_payload())
                if "perms" in changed:
                    perms = model.perms_payload()
                    hub.send("perms", perms)
                    flag = ui_dir(root) / "perm_open"  # tells the PostToolUse hook to report finished tools
                    flag.touch() if perms else flag.unlink(missing_ok=True)
        except FileNotFoundError:
            pass
        stop.wait(POLL)


def make_handler(root: Path, port: int, token: str, model: Model, hub: Hub):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    csp = ("default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; "
           "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")

    class Handler(BaseHTTPRequestHandler):
        server_version = "bma-ui"

        def log_message(self, fmt, *args):  # quiet; errors go to ui.log via stderr
            pass

        def _headers(self, code: int, ctype: str, extra: dict | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()

        def _deny(self, code: int = 403, msg: str = "forbidden") -> None:
            self._headers(code, "text/plain; charset=utf-8")
            self.wfile.write(msg.encode())

        def _token_ok(self, qs: dict) -> bool:
            got = self.headers.get("X-Token") or (qs.get("token") or [""])[0]
            return secrets.compare_digest(got.encode(), token.encode())

        def do_GET(self):
            if self.headers.get("Host") not in allowed_hosts:  # blocks DNS rebinding
                return self._deny(421, "wrong host")
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if u.path in ("/", "/index.html"):
                return self._static("index.html", {"Content-Security-Policy": csp})
            if u.path.startswith("/ui/"):
                return self._static(u.path[4:])
            if u.path == "/api/snapshot":
                if not self._token_ok(qs):
                    return self._deny()
                body = json.dumps(snapshot(root, model), ensure_ascii=False).encode()
                self._headers(200, "application/json; charset=utf-8")
                return self.wfile.write(body)
            if u.path == "/api/preview-shot":
                if not self._token_ok(qs):
                    return self._deny()
                pid = (qs.get("id") or [""])[0]
                if not any(p["id"] == pid for p in bma_preview.load(root)):
                    return self._deny(404, "not found")
                f = bma_preview.shots_dir(root) / f"{pid}.png"
                if not f.is_file():
                    return self._deny(404, "no screenshot")
                self._headers(200, "image/png")
                return self.wfile.write(f.read_bytes())
            if u.path == "/events":
                if not self._token_ok(qs):
                    return self._deny()
                return self._stream()
            return self._deny(404, "not found")

        def _read_json(self) -> dict | None:
            """Shared checks for POSTs from the page; sends the error and returns None on failure."""
            if self.headers.get("Host") not in allowed_hosts:
                return self._deny(421, "wrong host")
            origin = self.headers.get("Origin")
            if origin and origin.replace("http://", "") not in allowed_hosts:
                return self._deny(403, "wrong origin")
            # Token only in a header: a cross-site form can't set one, and a JSON body forces a preflight.
            if not secrets.compare_digest((self.headers.get("X-Token") or "").encode(), token.encode()):
                return self._deny()
            if (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
                return self._deny(415, "send JSON")
            length = int(self.headers.get("Content-Length") or 0)
            if length > 64 * 1024:
                return self._deny(413, "message too long")
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._deny(400, "bad JSON")
            return body if isinstance(body, dict) else self._deny(400, "bad JSON")

        def _ok(self, payload: dict):
            self._headers(200, "application/json; charset=utf-8")
            self.wfile.write(json.dumps(payload).encode())

        def do_POST(self):
            path = urlparse(self.path).path
            if path not in ("/api/chat", "/api/permission", "/api/answer", "/api/presence", "/api/preview"):
                return self._deny(404, "not found")
            body = self._read_json()
            if body is None:
                return
            if path == "/api/permission":
                return self._permission(body)
            if path == "/api/answer":
                return self._answer(body)
            if path == "/api/presence":
                return self._presence(body)
            if path == "/api/preview":
                return self._preview(body)
            text = str(body.get("text") or "").strip()
            if not text:
                return self._deny(400, "empty message")
            if len(text) > MAX_CHAT:
                return self._deny(413, f"Messages are limited to {MAX_CHAT} characters.")
            if not bridges(root)["chat"]:
                return self._deny(409, "No Claude Code session with chat turned on. Start Claude with: "
                                       "claude --dangerously-load-development-channels plugin:build-my-app@taro-tools")
            chat_id = f"w{int(time.time() * 1000) % 10**9}{secrets.randbelow(100):02d}"
            msg = {"chat_id": chat_id, "ts": round(time.time(), 3), "text": text}
            with open(ui_dir(root) / "inbox.jsonl", "a") as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
            append(root, {"ev": "prompt", "via": "web", "chat_id": chat_id, "text": text})
            self._ok({"chat_id": chat_id})

        def _preview(self, body: dict):
            items = bma_preview.load(root)
            p = next((x for x in items if x["id"] == str(body.get("id") or "")), None)
            if not p:
                return self._deny(404, "This preview is gone. Reload the page.")
            if body.get("action") == "shot":
                ok, msg = bma_preview.take_shot(root, p), "Screenshot updated."
            elif body.get("action") == "open":
                ok, msg = bma_preview.open_preview(root, p)
            else:
                return self._deny(400, "action must be open or shot")
            bma_preview.save(root, items)
            pv = previews(root, fresh=True)
            hub.send("previews", pv)
            if not ok:
                return self._deny(409, msg)
            self._ok({"ok": True, "message": msg})

        def _presence(self, body: dict):
            """The page says it is open (and whether it is visible); the question hook reads this."""
            touch_presence(root, visible=bool(body.get("visible")))
            self._ok({"ok": True})

        def _answer(self, body: dict):
            qid = str(body.get("qid") or "")
            q = model.open_question(qid)
            if not q:
                return self._deny(410, "This question is no longer waiting here. Check the terminal.")
            if body.get("terminal"):
                out = {"terminal": True}
            else:
                texts = [x["question"] for x in q["questions"]]
                raw = body.get("answers")
                if not isinstance(raw, dict):
                    return self._deny(400, "answers must be an object")
                answers = {t: str(raw.get(t) or "").strip()[:MAX_CHAT] for t in texts}
                if not all(answers.values()):
                    return self._deny(400, "Answer every question first.")
                out = {"answers": answers}
            if not model.claim(qid):
                return self._deny(410, "This question is no longer waiting here. Check the terminal.")
            if "answers" in out:
                model.answered(qid, answers)
            d = ui_dir(root) / "answers"
            d.mkdir(exist_ok=True)
            tmp = d / f"{qid}.tmp"
            tmp.write_text(json.dumps(out, ensure_ascii=False))
            os.replace(tmp, d / f"{qid}.json")
            self._ok({"ok": True})

        def _permission(self, body: dict):
            rid, behavior = str(body.get("request_id") or ""), body.get("behavior")
            if behavior not in ("allow", "deny"):
                return self._deny(400, "behavior must be allow or deny")
            p = model.open_perm(rid)
            if not p:
                return self._deny(410, "This request is no longer open. It was answered or Claude moved on.")
            if behavior == "allow" and p["hard"]:
                return self._deny(409, "This is a hard stop: allow it in the terminal. You can deny it here.")
            d = ui_dir(root) / "verdicts"
            d.mkdir(exist_ok=True)
            with open(d / f"{int(p['bridge'])}.jsonl", "a") as f:
                f.write(json.dumps({"request_id": rid, "behavior": behavior}) + "\n")
            self._ok({"ok": True})

        def _static(self, rel: str, extra: dict | None = None):
            p = (STATIC / rel).resolve()
            if STATIC.resolve() not in p.parents or not p.is_file() or p.suffix not in (".html", ".js", ".css", ".svg"):
                return self._deny(404, "not found")
            ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            self._headers(200, ctype, extra)
            self.wfile.write(p.read_bytes())

        def _stream(self):
            self._headers(200, "text/event-stream", {"Connection": "keep-alive"})
            q = hub.add()
            try:
                snap = snapshot(root, model)
                self.wfile.write(f"event: snapshot\ndata: {json.dumps(snap, ensure_ascii=False)}\n\n".encode())
                self.wfile.flush()
                while True:
                    try:
                        msg = q.get(timeout=15)
                    except queue.Empty:
                        msg = b": ping\n\n"
                    self.wfile.write(msg)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                hub.remove(q)

    return Handler


def serve(root: Path, port: int, token: str) -> None:
    d = ui_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    events_path(root).write_text("")  # each run starts with a fresh room
    (d / "inbox.jsonl").write_text("")
    (d / "inbox.offset").unlink(missing_ok=True)
    (d / "perm_open").unlink(missing_ok=True)
    (d / "presence.json").unlink(missing_ok=True)
    model, hub, stop = Model(), Hub(), threading.Event()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(root, port, token, model, hub))
    httpd.daemon_threads = True
    info = {"pid": os.getpid(), "port": port, "token": token, "url": f"http://127.0.0.1:{port}/?token={token}",
            "started": bma_state.now(), "version": plugin_version()}
    ip = ui_info_path(root)
    ip.write_text(json.dumps(info, indent=2) + "\n")
    os.chmod(ip, 0o600)

    def shutdown(*_):
        stop.set()
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    threading.Thread(target=watch, args=(root, model, hub, stop), daemon=True).start()
    try:
        httpd.serve_forever(poll_interval=0.5)
    finally:
        stop.set()
        try:
            if json.loads(ip.read_text()).get("pid") == os.getpid():
                ip.unlink()
        except Exception:
            pass


def free_port(start: int) -> int:
    for port in range(start, start + 50):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    sys.exit(f"No free port between {start} and {start + 49}. Pass --port.")


# -- commands -------------------------------------------------------------------

def cmd_start(a) -> None:
    root = project_root()
    if not (root / ".build-my-app" / "state.json").exists():
        sys.exit("No build-my-app state here. Run `/build-my-app:start` first.")
    info = read_info(root)
    if info and info.get("version") != plugin_version():
        # An older server keeps running the code it started with; the page it serves is newer.
        print(f"Restarting the UI server: it runs {('version ' + info['version']) if info.get('version') else 'an older version'}, "
              f"the plugin is {plugin_version()}. Open the new link below; the old one stops working.")
        cmd_stop(a)
        info = None
    if info:
        print(f"Already running: {info['url']}")
    else:
        port = a.port or free_port(DEFAULT_PORT)
        ui_dir(root).mkdir(parents=True, exist_ok=True)
        log = open(ui_dir(root) / "ui.log", "ab")
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root), BMA_UI_TOKEN=secrets.token_urlsafe(24))
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "serve", "--port", str(port)],
                         cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        for _ in range(50):
            time.sleep(0.1)
            info = read_info(root)
            if info:
                break
        if not info:
            sys.exit(f"The UI server did not start. See {ui_dir(root) / 'ui.log'}.")
        print(f"build-my-app UI: {info['url']}")
    time.sleep(1.5)  # give this session's chat bridge a moment to check in
    b = bridges(root)
    if b["chat"]:
        print("Chat is on: messages typed in the page go to this Claude Code session.")
    else:
        print("Watch-only: the page updates live. To chat from it too, start Claude Code with:\n"
              "  claude --dangerously-load-development-channels plugin:build-my-app@taro-tools")
    if a.open:
        webbrowser.open(info["url"])


def cmd_status(_a) -> None:
    info = read_info(project_root())
    print(f"Running (pid {info['pid']}): {info['url']}" if info else "Not running. Start it with `bma_ui.py start`.")


def cmd_stop(_a) -> None:
    root = project_root()
    info = read_info(root)
    if not info:
        ui_info_path(root).unlink(missing_ok=True)
        print("Not running.")
        return
    stopped = [p["label"] for p in bma_preview.load(root) if bma_preview.stop_owned(root, p)]
    if stopped:
        print("Stopped preview servers: " + ", ".join(stopped))
    os.kill(info["pid"], signal.SIGTERM)
    for _ in range(30):
        if not pid_alive(info["pid"]):
            break
        time.sleep(0.1)
    ui_info_path(root).unlink(missing_ok=True)
    print("Stopped.")


def cmd_serve(a) -> None:
    token = os.environ.get("BMA_UI_TOKEN")
    if not token:
        sys.exit("serve is started by `bma_ui.py start`.")
    serve(project_root(), a.port, token)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start"); s.add_argument("--port", type=int); s.add_argument("--open", action="store_true")
    sub.add_parser("status")
    sub.add_parser("stop")
    s = sub.add_parser("serve"); s.add_argument("--port", type=int, required=True)
    a = ap.parse_args()
    {"start": cmd_start, "status": cmd_status, "stop": cmd_stop, "serve": cmd_serve}[a.cmd](a)


if __name__ == "__main__":
    main()
