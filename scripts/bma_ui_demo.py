#!/usr/bin/env python3
"""Demo for the build-my-app web UI: a scripted build-phase story, played through the real
hook and event pipeline in a throwaway project, so you can watch the room without a real run.

  bma_ui_demo.py [--open] [--once] [--speed 1.5] [--dir PATH]

It creates a project in phase 4 (two features in progress, an open decision, a review loop),
starts the UI server, and replays the story in a loop until Ctrl-C. It also plays a stand-in
for the Claude Code session, so the page's interactive parts work: chat (canned replies), a
tool approval and a hard stop, a question from Claude, and a preview of the app to open. Nothing
touches your real projects,
your Claude Code sessions, or the machine-wide heavy-run slots. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bma_events import append  # noqa: E402

PLUGIN = Path(__file__).resolve().parents[1]
HOOK = PLUGIN / "hooks" / "ui_events.py"
ASK_HOOK = PLUGIN / "hooks" / "ask_web.py"
PFX = "build-my-app:"


def story(r: int) -> list[tuple]:
    """(seconds, action, payload). r makes agent ids unique per loop."""
    fb1, fb2, cr, ax, sr = (f"{n}-{r}" for n in ("fb1", "fb2", "cr", "ax", "sr"))
    def spawn(t, aid, typ, desc):
        return [(t, "hook", {"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_use_id": f"t-{aid}",
                             "tool_input": {"subagent_type": PFX + typ, "description": desc}}),
                (t + 0.6, "hook", {"hook_event_name": "SubagentStart", "agent_id": aid, "agent_type": PFX + typ})]
    def tool(t, aid, typ, name, ti):
        return (t, "hook", {"hook_event_name": "PreToolUse", "agent_id": aid, "agent_type": PFX + typ,
                            "tool_name": name, "tool_input": ti})
    def heavy(t, aid, typ, label):
        return tool(t, aid, typ, "Bash", {"command": f"python3 bma_heavy.py --label {label} -- swift test"})
    def stop(t, aid, typ, msg):
        return (t, "hook", {"hook_event_name": "SubagentStop", "agent_id": aid, "agent_type": PFX + typ,
                            "last_assistant_message": msg})
    def main_tool(t, name, ti):
        return (t, "hook", {"hook_event_name": "PreToolUse", "tool_name": name, "tool_input": ti})
    FB, CR, AX, SR = "feature-builder", "code-reviewer", "a11y-auditor", "stuck-resolver"
    return [
        (0, "state", ["step", "F-003 Streak pause and F-004 Reminders, in parallel"]),
        (0.5, "hook", {"hook_event_name": "UserPromptSubmit",
                       "prompt": "Continue the build. F-003 and F-004 don't depend on each other, so run them in parallel."}),
        main_tool(1.5, "Bash", {"command": "python3 bma_state.py next"}),
        main_tool(2.5, "Skill", {"skill": "build-my-app:build"}),
        *spawn(3.5, fb1, FB, "Implement F-003 Streak pause"),
        tool(5, fb1, FB, "Read", {"file_path": "specs/20-features/F-003-streak-pause.md"}),
        *spawn(6, fb2, FB, "Implement F-004 Reminders"),
        tool(7.5, fb2, FB, "Read", {"file_path": "specs/20-features/F-004-reminders.md"}),
        tool(8.5, fb1, FB, "Write", {"file_path": "Tests/StreakPauseTests.swift"}),
        (9, "ask", {"questions": [
            {"question": "When should a paused streak resume?", "header": "Streak pause",
             "options": [{"label": "On a date the user picks", "description": "Matches the F-003 spec draft"},
                         {"label": "After a fixed 7 days", "description": "Simpler; one less screen"}], "multiSelect": False},
            {"question": "Which reminder channels ship in the MVP?", "header": "Reminders",
             "options": [{"label": "Push"}, {"label": "Email"}, {"label": "Widget"}], "multiSelect": True}]}),
        tool(10, fb2, FB, "Read", {"file_path": "App/Notifications/ReminderScheduler.swift"}),
        heavy(11, fb1, FB, "F-003"), (11.5, "heavy", ("heavy_run", "F-003", None)),
        tool(12.5, fb2, FB, "Write", {"file_path": "Tests/ReminderTests.swift"}),
        heavy(14, fb2, FB, "F-004"), (14.5, "heavy", ("heavy_wait", "F-004", None)),
        (17, "heavy", ("heavy_done", "F-003", 1)), (17.3, "heavy", ("heavy_run", "F-004", None)),
        tool(18, fb1, FB, "Edit", {"file_path": "App/Streak/StreakEngine.swift"}),
        (19, "perm", ("Bash", "Install SwiftLint for the lint step", '{"command": "brew install swiftlint"}')),
        heavy(21, fb1, FB, "F-003"), (21.5, "heavy", ("heavy_wait", "F-003", None)),
        (23, "heavy", ("heavy_done", "F-004", 1)), (23.3, "heavy", ("heavy_run", "F-003", None)),
        tool(24, fb2, FB, "Edit", {"file_path": "App/Notifications/ReminderScheduler.swift"}),
        (27, "heavy", ("heavy_done", "F-003", 0)),
        stop(28, fb1, FB, "F-003 is green: 14 tests pass and all 4 acceptance criteria are covered.\nDetails...\nStatus: pass"),
        (28.5, "preview", "Dev build after F-003"),
        *spawn(29.5, cr, CR, "Review the F-003 diff"),
        tool(31, cr, CR, "Bash", {"command": "git diff main...HEAD", "description": "Read the F-003 diff"}),
        *spawn(32, ax, AX, "Audit SCR-Today"),
        tool(33.5, ax, AX, "Grep", {"pattern": "accessibilityLabel"}),
        heavy(34, fb2, FB, "F-004"), (34.5, "heavy", ("heavy_run", "F-004", None)),
        tool(35.5, cr, CR, "Read", {"file_path": "App/Streak/StreakEngine.swift"}),
        heavy(37, ax, AX, "SCR-Today"), (37.5, "heavy", ("heavy_wait", "SCR-Today", None)),
        (40, "heavy", ("heavy_done", "F-004", 1)), (40.3, "heavy", ("heavy_run", "SCR-Today", None)),
        tool(41, cr, CR, "Grep", {"pattern": "pausedUntil"}),
        (41.5, "perm", ("Bash", "Upload the build to TestFlight", '{"command": "fastlane pilot upload"}')),
        tool(42, fb2, FB, "Edit", {"file_path": "Tests/ReminderTests.swift"}),
        heavy(43, fb2, FB, "F-004"), (43.5, "heavy", ("heavy_wait", "F-004", None)),
        (45, "heavy", ("heavy_done", "SCR-Today", 0)), (45.3, "heavy", ("heavy_run", "F-004", None)),
        # two agents finish together: they line up at the front desk and hand over one at a time
        stop(46, ax, AX, "SCR-Today: the streak badge has no accessibility label; feature-builder should add one.\nStatus: fixes"),
        stop(46.4, cr, CR, "F-003 approved: the diff matches the spec and the tests cover every acceptance criterion.\nStatus: pass"),
        (49, "state", ["loop", "end", "review-F-003", "--outcome", "approved"]),
        (50, "heavy", ("heavy_done", "F-004", 1)),
        main_tool(51, "Bash", {"command": "python3 bma_state.py log 'F-004 failed 3 times'"}),
        *spawn(52, sr, SR, "Find out why the F-004 tests keep failing"),
        tool(53.5, sr, SR, "Read", {"file_path": "Tests/ReminderTests.swift"}),
        tool(55, sr, SR, "Grep", {"pattern": "TimeZone.current"}),
        stop(58, sr, SR, "The reminder test depends on the device time zone; inject a fixed clock."),  # no status: plain folder
        tool(59, fb2, FB, "Edit", {"file_path": "App/Notifications/ReminderScheduler.swift"}),
        heavy(60.5, fb2, FB, "F-004"), (61, "heavy", ("heavy_run", "F-004", None)),
        (65, "heavy", ("heavy_done", "F-004", 0)),
        stop(66, fb2, FB, "F-004 is green: 9 tests pass, with a fixed clock in the tests.\nStatus: pass"),
        (67, "state", ["step", "F-003 and F-004 done; next: F-005 Weekly summary"]),
        (68, "hook", {"hook_event_name": "Stop", "last_assistant_message":
                      "F-003 and F-004 are built and reviewed, and SCR-Today passes the accessibility audit. "
                      "Next is F-005 Weekly summary.\n\nOne decision is still waiting on you: paywall at launch."}),
        (68, "state", ["loop", "start", "review-F-003", "--max", "3"]),
        (78, "end", None),
    ]


def setup(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "feature/streaks"], cwd=root, check=False)
    st = lambda *a: run_state(root, *a)  # noqa: E731
    st("init", "--autonomy", "balanced")
    for pid in ("setup", "product-spec", "design", "architecture"):
        st("phase", pid, "in_progress"); st("gate", pid, "pass")
    st("phase", "build", "in_progress", "--step", "F-003 Streak pause and F-004 Reminders, in parallel")
    st("decide", "add", "Paywall at launch?", "--options", "Free|Freemium", "--recommend", "Free", "--kind", "money")
    st("loop", "start", "review-F-003", "--max", "3")
    st("set", "stack", json.dumps("iOS · SwiftUI · SwiftData"))
    st("set", "design_tool", json.dumps("Figma"))
    st("set", "environment", json.dumps({"xcode": "26.1", "simulator": "iPhone 17 (booted)", "swift": "6.2", "git": "2.47"}))


def run_state(root: Path, *args: str) -> None:
    subprocess.run([sys.executable, str(PLUGIN / "scripts" / "bma_state.py"), *args], cwd=root,
                   env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root)), capture_output=True, check=False)


MOCK_APP = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Habit Streaks (demo)</title>
<style>body{margin:0;font:16px/1.4 -apple-system,system-ui,sans-serif;background:#eef4f2;color:#1f2b2b}
header{background:#2f8f82;color:#fff;padding:18px 20px;font-weight:700;font-size:20px}
main{max-width:420px;margin:0 auto;padding:16px;display:grid;gap:12px}
.card{background:#fff;border-radius:14px;padding:14px 16px;display:flex;justify-content:space-between;align-items:center}
.n{font-size:22px;font-weight:700;color:#2f8f82}.p{font-size:13px;color:#5a6b6b}
button{font:inherit;border:0;border-radius:10px;padding:10px 14px;background:#2f8f82;color:#fff}
.note{font-size:13px;color:#5a6b6b;text-align:center}</style></head><body>
<header>Habit Streaks</header><main>
<div class="card"><div>Morning run<div class="p">Paused until Monday</div></div><div class="n">12 🔥</div></div>
<div class="card"><div>Read 20 pages<div class="p">Done today</div></div><div class="n">31 🔥</div></div>
<div class="card"><div>No sugar<div class="p">Not yet today</div></div><button>Check in</button></div>
<p class="note">Demo preview served by bma_ui_demo.py. In a real run, this is your app.</p>
</main></body></html>"""


def mock_png(path: Path) -> None:
    """A tiny stand-in screenshot of the mock app (header bar and three cards), no imaging library."""
    w, h = 360, 400
    bg, head, card, accent = (238, 244, 242), (47, 143, 130), (255, 255, 255), (47, 143, 130)
    rows = []
    for y in range(h):
        row = bytearray([0])
        for x in range(w):
            c = bg
            if y < 56:
                c = head
            else:
                for top in (76, 176, 276):
                    if top <= y < top + 84 and 16 <= x < w - 16:
                        c = accent if (w - 80 <= x < w - 36 and top + 30 <= y < top + 54) else card
            row += bytes(c)
        rows.append(bytes(row))
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(b"".join(rows), 6)) + chunk(b"IEND", b""))


class FakeSession:
    """Stands in for the Claude Code session: runs the real chat bridge with channels on, answers
    web messages with a canned reply, and raises approval prompts and a question."""

    def __init__(self, root: Path) -> None:
        self.root, self.env = root, dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
        self.bridge = subprocess.Popen([sys.executable, str(PLUGIN / "scripts" / "bma_channel.py")],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                       env=dict(self.env, BMA_CHANNEL="1"))
        self.lock, self.n = threading.Lock(), 0
        self._send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        threading.Thread(target=self._listen, daemon=True).start()

    def _send(self, msg: dict) -> None:
        with self.lock:
            try:
                self.bridge.stdin.write(json.dumps(msg) + "\n")
                self.bridge.stdin.flush()
            except (BrokenPipeError, ValueError):
                pass

    def hook(self, payload: dict) -> None:
        data = {"session_id": "demo", "cwd": str(self.root), **payload}
        subprocess.run([sys.executable, str(HOOK)], input=json.dumps(data), text=True, env=self.env, check=False)

    def _listen(self) -> None:
        for line in self.bridge.stdout:
            try:
                m = json.loads(line)
            except ValueError:
                continue
            if m.get("method") == "notifications/claude/channel":
                text = m["params"]["content"]
                threading.Thread(target=self._answer_chat, args=(text,), daemon=True).start()

    def _answer_chat(self, text: str) -> None:
        time.sleep(1.5)
        self._send({"jsonrpc": "2.0", "id": 99, "method": "tools/call",
                    "params": {"name": "reply", "arguments": {"text": "On it…"}}})
        time.sleep(2)
        self.hook({"hook_event_name": "Stop", "last_assistant_message":
                   f"(Demo) I got your message: \"{text[:120]}\". In a real session, Claude answers here "
                   "and does the work in the same conversation as the terminal."})

    def permission(self, tool: str, desc: str, preview: str) -> None:
        self.n += 1
        rid = "".join("abcdefghijkmnopqrstuvwxyz"[(self.n * 7 + i * 3) % 25] for i in range(5))
        self._send({"jsonrpc": "2.0", "method": "notifications/claude/channel/permission_request",
                    "params": {"request_id": rid, "tool_name": tool, "description": desc, "input_preview": preview}})

    def ask(self, tool_input: dict) -> None:
        def run():
            data = {"hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion", "cwd": str(self.root),
                    "tool_input": tool_input}
            out = subprocess.run([sys.executable, str(ASK_HOOK)], input=json.dumps(data), text=True,
                                 env=self.env, capture_output=True, check=False).stdout
            if out.strip():
                answers = json.loads(out)["hookSpecificOutput"]["updatedInput"]["answers"]
                self.hook({"hook_event_name": "Stop", "last_assistant_message":
                           "Thanks, noted: " + "; ".join(answers.values()) + ". (Demo: in a real session, "
                           "Claude continues with your answer and no terminal dialog opens.)"})
        threading.Thread(target=run, daemon=True).start()

    def preview(self, label: str) -> None:
        """Serve the mock app and record it as a preview, as Claude does after verifying a feature."""
        if not getattr(self, "app", None) or self.app.poll() is not None:
            site = self.root / "demo-app"
            site.mkdir(exist_ok=True)
            (site / "index.html").write_text(MOCK_APP)
            mock_png(site / "shot.png")
            s = socket.socket(); s.bind(("127.0.0.1", 0)); self.port = s.getsockname()[1]; s.close()
            self.app = subprocess.Popen([sys.executable, "-m", "http.server", str(self.port), "--bind", "127.0.0.1",
                                         "--directory", str(site)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.8)
        subprocess.run([sys.executable, str(PLUGIN / "scripts" / "bma_preview.py"), "add", "--kind", "web",
                        "--target", f"http://localhost:{self.port}/", "--label", label, "--cmd", "python3 -m http.server",
                        "--pid", str(self.app.pid), "--screenshot", str(self.root / "demo-app" / "shot.png")],
                       env=self.env, capture_output=True, check=False)

    def close(self) -> None:
        if getattr(self, "app", None):
            self.app.terminate()
        try:
            self.bridge.stdin.close()
            self.bridge.wait(5)
        except Exception:
            self.bridge.kill()


def play(root: Path, speed: float, r: int, session: FakeSession) -> None:
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
    start = time.time()
    for t, kind, payload in sorted(story(r), key=lambda x: x[0]):
        delay = start + t / speed - time.time()
        if delay > 0:
            time.sleep(delay)
        if kind == "hook":
            data = {"session_id": "demo", "cwd": str(root), **payload}
            subprocess.run([sys.executable, str(HOOK)], input=json.dumps(data), text=True, env=env, check=False)
        elif kind == "heavy":
            ev, label, code = payload
            append(root, {"ev": ev, "label": label, "pid": 0, **({"code": code} if code is not None else {})})
        elif kind == "state":
            run_state(root, *payload)
        elif kind == "perm":
            session.permission(*payload)
        elif kind == "ask":
            session.ask(payload)
        elif kind == "preview":
            session.preview(payload)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--open", action="store_true", help="open the page in the browser")
    ap.add_argument("--once", action="store_true", help="play the story once, then stop")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--dir", type=Path, help="project folder to use (default: a temporary one)")
    a = ap.parse_args()
    temp = a.dir is None
    root = (a.dir or Path(tempfile.mkdtemp(prefix="bma-ui-demo-")) / "habit-streaks").resolve()
    if (root / ".build-my-app").exists() and not temp:
        sys.exit(f"{root} already has build-my-app state. Pick an empty folder for the demo.")
    setup(root)
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
    ui = [sys.executable, str(PLUGIN / "scripts" / "bma_ui.py")]
    session = FakeSession(root)  # first, so the page finds a chat session as soon as it opens
    subprocess.run(ui + ["start"] + (["--open"] if a.open else []), env=env, cwd=root, check=True)
    print("Playing the demo story" + ("" if a.once else " in a loop") + ". Ctrl-C to stop.\n"
          "Try the chat box, the approval cards, and the question card (it appears while the page is in view).",
          flush=True)

    def finish(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, finish)
    try:
        r = 1
        while True:
            play(root, a.speed, r, session)
            if a.once:
                break
            r += 1
    except KeyboardInterrupt:
        pass
    finally:
        session.close()
        subprocess.run(ui + ["stop"], env=env, cwd=root, check=False, capture_output=True)
        if temp:
            shutil.rmtree(root.parent, ignore_errors=True)
        print("Demo stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
