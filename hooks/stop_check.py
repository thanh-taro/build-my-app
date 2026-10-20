#!/usr/bin/env python3
"""Stop: when the workflow is mid-phase, tell the user where it paused and how to resume.
Never blocks stopping."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import emit, is_bma_project, project_dir, read_input, state_cli  # noqa: E402


def main() -> None:
    data = read_input()
    if data.get("stop_hook_active"):
        return
    root = project_dir(data)
    if not is_bma_project(root):
        return
    nxt = state_cli(root, "next")
    if nxt.startswith(("CONTINUE", "GATE", "ASK")):
        emit({"systemMessage": f"build-my-app paused — {nxt.split(':', 1)[0].lower()} pending. "
                               "Resume with /build-my-app:start (status: /build-my-app:status)."})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
