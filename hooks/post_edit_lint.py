#!/usr/bin/env python3
"""PostToolUse (Edit/Write): after a spec edit, run the spec lint; feed errors back to Claude."""
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import has_spec_tools, project_dir, read_input  # noqa: E402


def main() -> None:
    data = read_input()
    root = project_dir(data)
    if not has_spec_tools(root):
        return
    file_path = (data.get("tool_input") or {}).get("file_path", "")
    try:
        Path(file_path).resolve().relative_to((root / "specs").resolve())
    except (ValueError, OSError):
        return
    r = subprocess.run([sys.executable, str(root / "tools" / "spec_lint.py"), "--quiet"],
                       capture_output=True, text=True, cwd=root, timeout=60)
    if r.returncode != 0:
        print("Spec lint failed after this edit — fix before continuing:\n" + r.stdout, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        pass
