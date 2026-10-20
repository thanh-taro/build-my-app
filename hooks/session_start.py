#!/usr/bin/env python3
"""SessionStart: in a build-my-app project, orient Claude with progress and the next step."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import emit, is_bma_project, project_dir, read_input, state_cli  # noqa: E402


def main() -> None:
    data = read_input()
    root = project_dir(data)
    if not is_bma_project(root):
        return
    status = state_cli(root, "status", "--short")
    nxt = state_cli(root, "next")
    ctx = (f"{status}\nNext: {nxt}\n"
           "This is a build-my-app project. Resume with /build-my-app:start; "
           "load the core skill before continuing workflow work.")
    emit({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
