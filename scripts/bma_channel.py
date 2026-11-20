#!/usr/bin/env python3
"""Chat bridge between the build-my-app web UI and the Claude Code session (an MCP channel).

Claude Code starts this server in every session where the plugin is enabled. It does nothing
unless all of these hold:
  - the project is a build-my-app project,
  - this Claude Code process was started with channels for the plugin
    (`--channels` or `--dangerously-load-development-channels` naming build-my-app),
  - the UI server is running (`/build-my-app:ui`).
Then it passes messages typed in the page into the session as channel events, gives Claude
a `reply` tool for short progress notes, and relays tool-approval prompts to the page (permission
relay). Hard stops (deploying, publishing, force-pushing, spending...) can be denied from the
page but only allowed in the terminal; this file enforces that, not just the page. Claude's final answer of each turn reaches the page
through the Stop hook, so nothing is lost if Claude answers in the terminal only.

Protocol: MCP over stdio, newline-delimited JSON-RPC, standard library only. Unknown requests
get a "method not found" error, which also makes Claude Code fall back from its newer
`server/discover` probe to `initialize` (channels need the older protocol revision).
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bma_events import append, clip, clip_text, ui_dir, ui_enabled  # noqa: E402

try:  # the bash guard's own patterns, so both agree on what ships something off the machine
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
    from pre_bash_guard import DEPLOY  # noqa: E402
except Exception:
    DEPLOY = None  # fail closed: every Bash request counts as a hard stop
FORCE_PUSH = r"\bgit\s+push\b.*(--force\b|\s-f\b|--force-with-lease\b)"
HARD_TOOL = re.compile(r"deploy|publish|release|submit|purchase|checkout|payment|pay_|charge|transfer|"
                       r"send_?(mail|email|message)|post_?(message|tweet)|credential|secret|password", re.I)

POLL = 0.5
HEARTBEAT = 5.0
PLUGIN_NAME = "build-my-app"

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
_out = threading.Lock()


def is_bma_project() -> bool:
    return (ROOT / ".build-my-app" / "state.json").exists()


def channel_enabled() -> bool:
    """True when an ancestor Claude Code process was started with channels for this plugin.
    Plugin MCP servers start in every session, but channel events only reach sessions that
    opted in; a bridge in any other session must not take messages it would drop."""
    forced = os.environ.get("BMA_CHANNEL")
    if forced is not None:
        return forced == "1"
    pid = os.getppid()
    for _ in range(8):
        try:
            out = subprocess.run(["ps", "-o", "ppid=,command=", "-p", str(pid)], capture_output=True,
                                 text=True, timeout=3).stdout.strip()
        except Exception:
            return False
        if not out:
            return False
        ppid, _, cmd = out.partition(" ")
        if ("--channels" in cmd or "--dangerously-load-development-channels" in cmd) and PLUGIN_NAME in cmd:
            return True
        try:
            pid = int(ppid)
        except ValueError:
            return False
        if pid <= 1:
            return False
    return False


ACTIVE = is_bma_project()
CHANNEL = ACTIVE and channel_enabled()
PENDING: dict[str, dict] = {}   # open permission requests relayed to the page: request_id → {hard}


def hard_stop(tool: str, description: str, preview: str) -> str | None:
    """Why this request must be allowed in the terminal, or None if the page may allow it."""
    if tool == "Bash":
        if DEPLOY is None:
            return "The hard-stop check is unavailable, so the terminal decides."
        if re.search(DEPLOY, preview) or re.search(r"deploy|publish", description, re.I):
            return "This deploys, publishes, or submits something (hard stop)."
        if re.search(FORCE_PUSH, preview):
            return "Force push rewrites shared history (hard stop)."
        return None
    if HARD_TOOL.search(tool):
        return f"{tool} may spend money, publish, send, or handle secrets (hard stop)."
    return None

INSTRUCTIONS = (
    'Messages the user types in the build-my-app web page arrive as <channel source="..." chat_id="...">. '
    "They come from the same user as the terminal: treat them exactly like terminal messages. "
    "The page shows your final message of every turn automatically, so answer normally. "
    "Use the `reply` tool only for a short progress note before long work (for example "
    "\"On it: starting F-005\"), never to repeat your final answer."
    if CHANNEL else
    "build-my-app web chat is off in this session (not a build-my-app project, or Claude Code was not "
    "started with channels for build-my-app). This server has no tools here."
)
TOOLS = [{
    "name": "reply",
    "description": "Show a short progress note in the build-my-app web page's chat. Your final answer "
                   "reaches the page on its own; do not repeat it here.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The note, one or two sentences."},
            "chat_id": {"type": "string", "description": "chat_id from the <channel> tag, if answering one"},
        },
        "required": ["text"],
    },
}]


def write(msg: dict) -> None:
    line = json.dumps(msg, ensure_ascii=False)
    with _out:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


def handle(msg: dict) -> None:
    method, mid = msg.get("method"), msg.get("id")
    if method == "initialize":
        write({"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": (msg.get("params") or {}).get("protocolVersion", "2025-06-18"),
            "capabilities": {"experimental": {"claude/channel": {}, "claude/channel/permission": {} if CHANNEL else False},
                             "tools": {}},
            "serverInfo": {"name": "bma", "version": "0.5.0"},
            "instructions": INSTRUCTIONS,
        }})
    elif method == "tools/list":
        write({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS if CHANNEL else []}})
    elif method == "tools/call":
        p = msg.get("params") or {}
        if p.get("name") == "reply" and CHANNEL:
            a = p.get("arguments") or {}
            if ui_enabled(ROOT):
                append(ROOT, {"ev": "reply", "via": "web", "interim": True, "chat_id": a.get("chat_id"),
                              "text": clip_text(a.get("text"), 1200)})
                result = "Shown in the web page."
            else:
                result = "The web page is closed; nothing was shown. Answer in the terminal."
            write({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": result}]}})
        else:
            write({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "unknown tool"}})
    elif method == "notifications/claude/channel/permission_request" and CHANNEL:
        p = msg.get("params") or {}
        rid = str(p.get("request_id") or "")
        if not re.fullmatch(r"[a-km-z]{5}", rid):
            return
        tool, desc, preview = (str(p.get(k) or "") for k in ("tool_name", "description", "input_preview"))
        reason = hard_stop(tool, desc, preview)
        PENDING[rid] = {"hard": bool(reason), "ts": time.time()}
        for old in [k for k, v in PENDING.items() if time.time() - v["ts"] > 3600]:
            PENDING.pop(old, None)
        if ui_enabled(ROOT):
            append(ROOT, {"ev": "permission", "request_id": rid, "tool": tool, "desc": clip(desc, 300),
                          "preview": clip_text(preview, 1500), "hard": bool(reason), "reason": reason,
                          "bridge": os.getpid()})
    elif method == "ping":
        write({"jsonrpc": "2.0", "id": mid, "result": {}})
    elif mid is not None:
        write({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}})


# -- inbox → session -------------------------------------------------------------

def bridge_file() -> Path:
    return ui_dir(ROOT) / "bridges" / f"{os.getpid()}.json"


def heartbeat() -> None:
    p = bridge_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"pid": os.getpid(), "channel": CHANNEL, "ts": time.time()}))
    os.replace(tmp, p)


def deliver_new() -> None:
    """Take unread inbox lines (one bridge at a time) and push each into the session."""
    d = ui_dir(ROOT)
    inbox, offset_file = d / "inbox.jsonl", d / "inbox.offset"
    if not inbox.exists():
        return
    with open(d / "inbox.lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            try:
                offset = int(offset_file.read_text() or 0)
            except (FileNotFoundError, ValueError):
                offset = 0
            data = inbox.read_bytes()
            if offset > len(data):
                offset = 0  # the server restarted and cleared the inbox
            chunk = data[offset:]
            end = chunk.rfind(b"\n") + 1
            if end <= 0:
                return
            offset_file.write_text(str(offset + end))
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
    for line in chunk[:end].splitlines():
        try:
            m = json.loads(line)
        except ValueError:
            continue
        write({"jsonrpc": "2.0", "method": "notifications/claude/channel",
               "params": {"content": m.get("text", ""), "meta": {"chat_id": str(m.get("chat_id", "")), "sender": "web"}}})
        append(ROOT, {"ev": "delivered", "chat_id": m.get("chat_id"), "bridge": os.getpid()})


def verdicts_file() -> Path:
    return ui_dir(ROOT) / "verdicts" / f"{os.getpid()}.jsonl"


def apply_verdicts() -> None:
    """Answers clicked in the page for this session's permission prompts."""
    f = verdicts_file()
    if not f.exists():
        return
    taking = f.with_suffix(".taking")
    os.replace(f, taking)  # atomic hand-off: the server appends to a fresh file from now on
    lines = taking.read_text().splitlines()
    taking.unlink()
    for line in lines:
        try:
            v = json.loads(line)
        except ValueError:
            continue
        rid, behavior = str(v.get("request_id")), v.get("behavior")
        req = PENDING.get(rid)
        if not req or behavior not in ("allow", "deny"):
            continue
        if behavior == "allow" and req["hard"]:
            append(ROOT, {"ev": "permission_refused", "request_id": rid})
            continue
        PENDING.pop(rid, None)
        write({"jsonrpc": "2.0", "method": "notifications/claude/channel/permission",
               "params": {"request_id": rid, "behavior": behavior}})
        append(ROOT, {"ev": "permission_answer", "request_id": rid, "behavior": behavior, "via": "web"})


def pump(stop: threading.Event) -> None:
    last_beat = 0.0
    while not stop.is_set():
        try:
            if ui_enabled(ROOT):
                if time.time() - last_beat > HEARTBEAT or not bridge_file().exists():
                    heartbeat()
                    last_beat = time.time()
                if CHANNEL:
                    deliver_new()
                    apply_verdicts()
        except Exception as e:  # keep the session's MCP connection alive no matter what
            print(f"bma_channel: {e!r}", file=sys.stderr, flush=True)
        stop.wait(POLL)


def main() -> None:
    stop = threading.Event()
    if ACTIVE:
        threading.Thread(target=pump, args=(stop,), daemon=True).start()
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                handle(json.loads(line))
            except Exception as e:
                print(f"bma_channel: bad message {e!r}", file=sys.stderr, flush=True)
    finally:
        stop.set()
        for f in (bridge_file(), verdicts_file()):
            try:
                f.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    main()
