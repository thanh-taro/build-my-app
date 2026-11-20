#!/usr/bin/env python3
"""build-my-app web UI server (v0.3: watch only). Standard library only.

  bma_ui.py start [--port N] [--open]   Start in the background and print the URL
  bma_ui.py status                      Print whether it runs, and its URL
  bma_ui.py stop                        Stop it

Serves the room (ui/), a snapshot API, and a server-sent event stream on 127.0.0.1 only.
Every API and stream request needs the random token in the URL that `start` prints.
While it runs, `ui.json` in `.build-my-app/tmp/ui/` tells the hooks to record events;
the server tails that event log and `state.json` and pushes changes to the browser.
Chat from the browser arrives in v0.4 (Claude Code channels); for now, type in the terminal.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import queue
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
import bma_state  # noqa: E402
from bma_events import clip, events_path, lower_first, ui_dir, ui_info_path  # noqa: E402
from bma_resources import memory_state  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
STATIC = PLUGIN_ROOT / "ui"
DEFAULT_PORT = 7311
POLL = 0.4
DONE_KEEP = 40          # finished agents kept for the timeline
STUCK_AFTER = 3         # consecutive failed heavy runs before an agent shows as stuck


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

    def take_fresh(self) -> list[dict]:
        with self.lock:
            out, self.fresh = self.fresh, []
            return out

    # Each apply returns the kinds of change it made: {"agents", "feed"}.
    def apply(self, e: dict) -> set[str]:
        with self.lock:
            return self._apply(e)

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
            a = self._agent(aid, e.get("type"), ts)
            result = clip((e.get("text") or "").split("\n")[0], 200)
            a.update(status="done", result=result, now=result or "Finished", updated=ts, ended=ts)
            self._say(a["type"], result or "Finished.", ts, kind="done", agent=aid)
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
            self._say("you", e.get("text") or "", ts, via=e.get("via") or "terminal")
            return {"feed"}
        if ev == "reply" and not aid:
            self.assistant = {"now": "", "ts": ts}
            self._say("assistant", e.get("text") or "", ts, kind="reply")
            return {"agents", "feed"}
        return set()

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


def watch(root: Path, model: Model, hub: Hub, stop: threading.Event) -> None:
    sp, ep = root / ".build-my-app" / "state.json", events_path(root)
    state_mtime, offset, last_pressure, last_push = 0.0, 0, None, 0.0
    while not stop.is_set():
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
                if "agents" in changed:
                    hub.send("agents", model.agents_payload())
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
                body = json.dumps({"state": state_payload(root), **model.agents_payload(),
                                   "feed": model.feed_payload()}, ensure_ascii=False).encode()
                self._headers(200, "application/json; charset=utf-8")
                return self.wfile.write(body)
            if u.path == "/events":
                if not self._token_ok(qs):
                    return self._deny()
                return self._stream()
            return self._deny(404, "not found")

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
                snap = {"state": state_payload(root), **model.agents_payload(), "feed": model.feed_payload()}
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
    model, hub, stop = Model(), Hub(), threading.Event()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(root, port, token, model, hub))
    httpd.daemon_threads = True
    info = {"pid": os.getpid(), "port": port, "token": token, "url": f"http://127.0.0.1:{port}/?token={token}",
            "started": bma_state.now()}
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
    print("Watch-only for now: the room, the feed, and the status panel update live. Keep chatting in the terminal.")
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
