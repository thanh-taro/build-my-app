#!/usr/bin/env python3
"""PreToolUse (Bash): in build-my-app projects, stop destructive commands and unregistered
dependency installs (licensing policy)."""
import re
import shlex
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ask, deny, is_bma_project, project_dir, read_input  # noqa: E402

DENY = [
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+(/|~|\$HOME)(\s|$)", "Refusing to delete the root or home directory."),
]
ASK = [
    (r"\bgit\s+push\b.*(--force\b|\s-f\b|--force-with-lease\b)", "Force push rewrites shared history (hard stop)."),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard discards uncommitted work."),
    (r"\bgit\s+clean\s+-[a-zA-Z]*f", "git clean -f deletes untracked files."),
    (r"\b(xcrun\s+altool|xcrun\s+notarytool|fastlane\s+(deliver|pilot|supply)|eas\s+submit|vercel\s+--prod|firebase\s+deploy)\b",
     "This publishes or submits the app (release hard stop)."),
]
# package manager install commands → package names that follow
INSTALL = [
    (r"\bnpm\s+(?:i|install|add)\s+(.+)", "npm"),
    (r"\bpnpm\s+(?:add|install)\s+(.+)", "pnpm"),
    (r"\byarn\s+add\s+(.+)", "yarn"),
    (r"\bbun\s+add\s+(.+)", "bun"),
    (r"\bpip3?\s+install\s+(.+)", "pip"),
    (r"\bcargo\s+add\s+(.+)", "cargo"),
    (r"\bpod\s+'?([A-Za-z0-9_\-]+)", "pod"),
]


def registered_names(root: Path) -> str:
    reg = root / "specs" / "40-technical" / "dependencies.md"
    return reg.read_text().lower() if reg.exists() else ""


def package_names(arg_str: str) -> list[str]:
    try:
        parts = shlex.split(arg_str)
    except ValueError:
        parts = arg_str.split()
    names = []
    for p in parts:
        if p.startswith("-") or p in ("&&", "||", ";", "|"):
            if p in ("&&", "||", ";", "|"):
                break
            continue
        if p.startswith(("./", "/", ".", "git+", "http")) or p.endswith((".txt", ".toml")):
            continue
        name = re.split(r"(?<=.)@|==|>=|<=|~=", p)[0]
        names.append(name)
    return names


def main() -> None:
    data = read_input()
    root = project_dir(data)
    if not is_bma_project(root):
        return
    cmd = (data.get("tool_input") or {}).get("command", "")
    for pattern, reason in DENY:
        if re.search(pattern, cmd):
            deny(reason)
            return
    for pattern, reason in ASK:
        if re.search(pattern, cmd):
            ask(reason)
            return
    reg = registered_names(root)
    for pattern, _tool in INSTALL:
        m = re.search(pattern, cmd)
        if not m:
            continue
        missing = [n for n in package_names(m.group(1)) if n.lower() not in reg]
        if missing:
            ask(f"Not in the dependency registry: {', '.join(missing)}. Per the licensing policy, "
                "audit the license (license-auditor) and register it in "
                "specs/40-technical/dependencies.md before installing.")
            return


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
