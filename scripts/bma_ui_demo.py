#!/usr/bin/env python3
"""Demo for the build-my-app web UI: a scripted build-phase story, played through the real
hook and event pipeline in a throwaway project, so you can watch the room without a real run.

  bma_ui_demo.py [--open] [--once] [--speed 1.5] [--dir PATH]

It creates a project in phase 4 (two features in progress, an open decision, a review loop),
starts the UI server, and replays the story in a loop until Ctrl-C. Nothing touches your
real projects or the machine-wide heavy-run slots. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bma_events import append  # noqa: E402

PLUGIN = Path(__file__).resolve().parents[1]
HOOK = PLUGIN / "hooks" / "ui_events.py"
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
        tool(10, fb2, FB, "Read", {"file_path": "App/Notifications/ReminderScheduler.swift"}),
        heavy(11, fb1, FB, "F-003"), (11.5, "heavy", ("heavy_run", "F-003", None)),
        tool(12.5, fb2, FB, "Write", {"file_path": "Tests/ReminderTests.swift"}),
        heavy(14, fb2, FB, "F-004"), (14.5, "heavy", ("heavy_wait", "F-004", None)),
        (17, "heavy", ("heavy_done", "F-003", 1)), (17.3, "heavy", ("heavy_run", "F-004", None)),
        tool(18, fb1, FB, "Edit", {"file_path": "App/Streak/StreakEngine.swift"}),
        heavy(21, fb1, FB, "F-003"), (21.5, "heavy", ("heavy_wait", "F-003", None)),
        (23, "heavy", ("heavy_done", "F-004", 1)), (23.3, "heavy", ("heavy_run", "F-003", None)),
        tool(24, fb2, FB, "Edit", {"file_path": "App/Notifications/ReminderScheduler.swift"}),
        (27, "heavy", ("heavy_done", "F-003", 0)),
        stop(28, fb1, FB, "F-003 is green: 14 tests pass and all 4 acceptance criteria are covered.\nDetails..."),
        *spawn(29.5, cr, CR, "Review the F-003 diff"),
        tool(31, cr, CR, "Bash", {"command": "git diff main...HEAD", "description": "Read the F-003 diff"}),
        *spawn(32, ax, AX, "Audit SCR-Today"),
        tool(33.5, ax, AX, "Grep", {"pattern": "accessibilityLabel"}),
        heavy(34, fb2, FB, "F-004"), (34.5, "heavy", ("heavy_run", "F-004", None)),
        tool(35.5, cr, CR, "Read", {"file_path": "App/Streak/StreakEngine.swift"}),
        heavy(37, ax, AX, "SCR-Today"), (37.5, "heavy", ("heavy_wait", "SCR-Today", None)),
        (40, "heavy", ("heavy_done", "F-004", 1)), (40.3, "heavy", ("heavy_run", "SCR-Today", None)),
        tool(41, cr, CR, "Grep", {"pattern": "pausedUntil"}),
        tool(42, fb2, FB, "Edit", {"file_path": "Tests/ReminderTests.swift"}),
        heavy(43, fb2, FB, "F-004"), (43.5, "heavy", ("heavy_wait", "F-004", None)),
        (45, "heavy", ("heavy_done", "SCR-Today", 0)), (45.3, "heavy", ("heavy_run", "F-004", None)),
        stop(46, ax, AX, "SCR-Today passes contrast and Dynamic Type; I added 1 missing label."),
        stop(48, cr, CR, "F-003 approved after 2 small fixes."),
        (49, "state", ["loop", "end", "review-F-003", "--outcome", "approved"]),
        (50, "heavy", ("heavy_done", "F-004", 1)),
        main_tool(51, "Bash", {"command": "python3 bma_state.py log 'F-004 failed 3 times'"}),
        *spawn(52, sr, SR, "Find out why the F-004 tests keep failing"),
        tool(53.5, sr, SR, "Read", {"file_path": "Tests/ReminderTests.swift"}),
        tool(55, sr, SR, "Grep", {"pattern": "TimeZone.current"}),
        stop(58, sr, SR, "The reminder test depends on the device time zone; inject a fixed clock."),
        tool(59, fb2, FB, "Edit", {"file_path": "App/Notifications/ReminderScheduler.swift"}),
        heavy(60.5, fb2, FB, "F-004"), (61, "heavy", ("heavy_run", "F-004", None)),
        (65, "heavy", ("heavy_done", "F-004", 0)),
        stop(66, fb2, FB, "F-004 is green: 9 tests pass, with a fixed clock in the tests."),
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


def play(root: Path, speed: float, r: int) -> None:
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
    subprocess.run(ui + ["start"] + (["--open"] if a.open else []), env=env, cwd=root, check=True)
    print("Playing the demo story" + ("" if a.once else " in a loop") + ". Ctrl-C to stop.", flush=True)

    def finish(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, finish)
    try:
        r = 1
        while True:
            play(root, a.speed, r)
            if a.once:
                break
            r += 1
    except KeyboardInterrupt:
        pass
    finally:
        subprocess.run(ui + ["stop"], env=env, cwd=root, check=False, capture_output=True)
        if temp:
            shutil.rmtree(root.parent, ignore_errors=True)
        print("Demo stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
