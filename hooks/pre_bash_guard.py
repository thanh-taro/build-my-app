#!/usr/bin/env python3
"""PreToolUse (Bash): in build-my-app projects, stop destructive commands, deploy/publish
commands before the deploy phase (local-first), heavy build/test commands that bypass the
resource wrapper or start watch mode (resource budget), and unregistered dependency installs
(licensing policy)."""
import json
import re
import shlex
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PLUGIN_ROOT, ask, deny, is_bma_project, project_dir, read_input, state_file  # noqa: E402

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


# Resource budget (skills/core/protocols/resources.md). A heavy tool counts only in command
# position: start of the command, after a separator, or after a runner prefix such as npx.
CMD_START = (r"(?:^|[;&|(]\s*|\b(?:then|do|else)\s+)(?:\w+=\S*\s+)*"
             r"(?:(?:time|env|nice|command|npx|bunx|pnpm\s+(?:exec|dlx)|yarn\s+dlx|uv\s+run|poetry\s+run"
             r"|bundle\s+exec|python3?\s+-m)\s+)*")
HEAVY = CMD_START + (
    r"(?:xcodebuild\b(?![^;&|]*\s-(?:version|list|showsdks|showBuildSettings|showdestinations)\b)"
    r"|(?:\./)?gradlew?\s[^;&|]*?(?:assemble|build|[tT]est|bundle|check|connected|lint)"
    r"|(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?(?:test|build|e2e|check)(?::\S+)?(?=\s|$|[;&|)])"
    r"|vitest\b|jest\b|playwright\s+test\b|cypress\s+run\b|pytest\b|go\s+test\b"
    r"|cargo\s+(?:test|build|nextest)\b|swift\s+(?:test|build)\b|dotnet\s+(?:test|build)\b"
    r"|mvn\b[^;&|]*\b(?:test|verify|package|install)\b|flutter\s+(?:test|build)\b"
    r"|make\b[^;&|]*?\b(?:test|build|e2e|check)\b)")
WATCH = r"--watch(?:All)?\b(?!=false)|\bvitest\s+(?:watch|dev)\b|\bptw\b"


def enforce_heavy(root: Path) -> bool:
    try:
        return json.loads(state_file(root).read_text()).get("enforce_heavy", True) is not False
    except Exception:
        return True


def resource_violation(cmd: str) -> str | None:
    if re.search(WATCH, cmd):
        return ("Resource budget: watch mode never exits and keeps holding memory (and a heavy slot). "
                "Run the tests once instead (e.g. `vitest run`, no `--watch`).")
    if "bma_heavy.py" in cmd or not re.search(HEAVY, cmd):
        return None
    wrapped = f"python3 {PLUGIN_ROOT / 'scripts' / 'bma_heavy.py'} --label <task> -- {shlex.quote(cmd)}"
    return ("Resource budget: builds and test runs must go through the heavy-run wrapper, which "
            "limits concurrent runs across agents, caps test workers, and stops on critical memory "
            f"pressure. Re-run as:\n  {wrapped}\nWhile iterating, narrow it to the affected tests. "
            "(The user can turn this check off with `bma_state.py set enforce_heavy false`.)")


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
    if enforce_heavy(root):
        reason = resource_violation(cmd)
        if reason:
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
