#!/usr/bin/env python3
"""PreToolUse (Edit/Write): protect workflow state and generated files in build-my-app projects."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import deny, is_bma_project, project_dir, read_input  # noqa: E402

GENERATED_MARKERS = ("GENERATED FROM specs", "@generated from specs")


def main() -> None:
    data = read_input()
    root = project_dir(data)
    if not is_bma_project(root):
        return
    path = Path((data.get("tool_input") or {}).get("file_path", ""))
    if not path.name:
        return
    if path.resolve() == (root / ".build-my-app" / "state.json").resolve():
        deny("Workflow state is managed by the state CLI: "
             "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_state.py (see core).")
        return
    if path.exists() and path.is_file():
        try:
            head = "".join(path.open(errors="ignore").readlines()[:5])
        except OSError:
            return
        if any(m in head for m in GENERATED_MARKERS):
            deny(f"{path.name} is generated from specs. Change the spec source and regenerate "
                 "(see adapters/codegen.md) instead of editing it by hand.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
