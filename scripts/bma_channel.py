#!/usr/bin/env python3
"""Chat bridge between the build-my-app web UI and the Claude Code session (an MCP channel).

Claude Code starts this server in every session where the plugin is enabled. It does nothing
unless all of these hold:
  - the project is a build-my-app project,
  - this Claude Code process was started with channels for the plugin
    (`--channels` or `--dangerously-load-development-channels` naming build-my-app),
  - the UI server is running (`/build-my-app:ui`).
Then it passes messages typed in the page into the session as channel events, and gives Claude
a `reply` tool for short progress notes. Claude's final answer of each turn reaches the page
through the Stop hook, so nothing is lost if Claude answers in the terminal only.

Protocol: MCP over stdio, newline-delimited JSON-RPC, standard library only. Unknown requests
get a "method not found" error, which also makes Claude Code fall back from its newer
`server/discover` probe to `initialize` (channels need the older protocol revision).
"""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bma_events import append, clip_text, ui_dir, ui_enabled  # noqa: E402

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
            "capabilities": {"experimental": {"claude/channel": {}}, "tools": {}},
            "serverInfo": {"name": "bma", "version": "0.4.0"},
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
        try:
            bridge_file().unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()
