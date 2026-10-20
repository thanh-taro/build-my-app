#!/usr/bin/env python3
"""PreCompact: record the compaction point in the workflow log so the run can be re-oriented."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import is_bma_project, project_dir, read_input, state_cli  # noqa: E402


def main() -> None:
    data = read_input()
    root = project_dir(data)
    if not is_bma_project(root):
        return
    status = state_cli(root, "status", "--short").splitlines()
    state_cli(root, "log", f"context compaction ({data.get('trigger', 'auto')}) at: {status[0] if status else '?'}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
