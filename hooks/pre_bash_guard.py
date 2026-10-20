#!/usr/bin/env python3
"""PreToolUse (Bash): in build-my-app projects, stop destructive commands, deploy/publish
commands before the deploy phase (local-first), and unregistered dependency installs
(licensing policy)."""
import json
import re
import shlex
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ask, deny, is_bma_project, project_dir, read_input, state_file  # noqa: E402

DENY = [
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+(/|~|\$HOME)(\s|$)", "Refusing to delete the root or home directory."),
]
ASK = [
    (r"\bgit\s+push\b.*(--force\b|\s-f\b|--force-with-lease\b)", "Force push rewrites shared history (hard stop)."),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard discards uncommitted work."),
    (r"\bgit\s+clean\s+-[a-zA-Z]*f", "git clean -f deletes untracked files."),
    ]
# Commands that ship something off the machine (deploy, publish, submit, provision).
DEPLOY = (r"\b(xcrun\s+altool|xcrun\s+notarytool|fastlane\s+(deliver|pilot|supply|upload_to_\w+)"
          r"|eas\s+(submit|update)|vercel(\s+deploy|\s+--prod|\s*$)|netlify\s+deploy|firebase\s+deploy"
          r"|fly(ctl)?\s+deploy|gcloud\s+(app|run|functions)\s+deploy|wrangler\s+(deploy|publish|pages\s+deploy)"
          r"|railway\s+up|heroku\s+(container:release|create|apps:create)|git\s+push\s+heroku|aws\s+(s3\s+sync|cloudformation\s+deploy|amplify)"
          r"|sam\s+deploy|cdk\s+deploy|serverless\s+deploy|sls\s+deploy|terraform\s+apply|pulumi\s+up"
          r"|docker\s+push|npm\s+publish|gh\s+release\s+create)\b")


def deploy_phase_started(root: Path) -> bool:
    try:
        phases = json.loads(state_file(root).read_text())["phases"]
    except Exception:
        return True  # fail open: unknown state → fall back to asking
    return phases.get("deploy", {}).get("status", "pending") != "pending"


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
    if re.search(DEPLOY, cmd):
        if not deploy_phase_started(root):
            deny("Local-first: nothing is deployed, published, or provisioned before phase 7 (deploy). "
                 "Develop and verify on the local environment; ship through the release and deploy phases.")
        else:
            ask("This deploys, publishes, or submits the app (deploy hard stop) — the user must approve.")
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
