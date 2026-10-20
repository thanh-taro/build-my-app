#!/usr/bin/env python3
"""UserPromptSubmit: when a prompt mentions spec IDs, inject their titles and locations."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import emit, has_spec_tools, project_dir, read_input  # noqa: E402

MAX_IDS = 15


def main() -> None:
    data = read_input()
    root = project_dir(data)
    if not has_spec_tools(root) or not (root / "tools" / "specs_index.py").exists():
        return
    sys.path.insert(0, str(root / "tools"))
    from specs_index import Index  # project-vendored spec tooling
    ix = Index()
    ids = ix.ids_in(data.get("prompt", ""))
    if not ids:
        return
    lines = ["Spec IDs mentioned in this prompt (source of truth: specs/):"]
    for id_ in ids[:MAX_IDS]:
        d = ix.get(id_)
        if d:
            status = f" [{d.meta['status']}]" if d.meta.get("status") else ""
            lines.append(f"- {id_} — {d.title}{status} ({d.rel}:{d.line})")
        else:
            lines.append(f"- {id_} — NOT DEFINED in specs/ (ask the user or propose a spec)")
    lines.append("Load full context with: python3 tools/spec_query.py context <ID>  (spec-context skill).")
    emit({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "\n".join(lines)}})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
