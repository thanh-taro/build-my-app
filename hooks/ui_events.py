#!/usr/bin/env python3
"""UI event recorder (async hook): turns hook input into short, human-readable events for the
build-my-app web UI. A no-op unless the UI server is running in this project.

Registered for SubagentStart, SubagentStop, PreToolUse and PostToolUse (all tools),
UserPromptSubmit, and Stop. It records what an agent is doing in a few words, never file
contents or full commands.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from _common import is_bma_project, project_dir, read_input  # noqa: E402
from bma_events import append, clip, clip_text, lower_first, ui_dir, ui_enabled  # noqa: E402

AGENT_TOOLS = ("Agent", "Task")
LABEL_RE = re.compile(r"bma_heavy\.py\b.*?--label[ =]([^\s'\"]+)")
# An agent's report outcome: its "Status: pass|fixes|blocked" line, else a guess from its words.
STATUS_RE = re.compile(r"^[\s>*_`-]*status[*_`]*\s*:\s*[*_`]*\s*(pass|fixes|blocked)\b", re.I | re.M)
NEGATED_RE = re.compile(r"\b(?:0|no|zero|none|without)\s+(?:\w+\s+){0,2}?(?:failed|failing|failures?|issues?|findings?|"
                        r"blockers?|blocking|bugs?|problems?|errors?)\b", re.I)
BLOCKED_RE = re.compile(r"\b(blocked|cannot proceed|can't proceed|could not|couldn't|unable to|gave up|"
                        r"still fail(?:s|ing)?|failed|failing)\b", re.I)
FIXES_RE = re.compile(r"\b(findings?|issues? found|found \d+ (?:issues?|problems?|bugs?)|needs? (?:\d+ )?(?:\w+ )?(?:fix(?:es|ing)?|changes)|"
                      r"changes requested|request(?:ed|ing)? changes|must fix|should fix|bugs? found|violations?)\b", re.I)
PASS_RE = re.compile(r"\b(green|pass(?:es|ed)?|approved?|lgtm|looks good|all (?:tests|checks) pass|done|completed?)\b", re.I)


def outcome(text: str) -> str | None:
    """pass, fixes, blocked, or None when it can't be told."""
    m = STATUS_RE.search(text)
    if m:
        return m.group(1).lower()
    words = NEGATED_RE.sub(" ", text[:3000])
    for name, rx in (("blocked", BLOCKED_RE), ("fixes", FIXES_RE), ("pass", PASS_RE)):
        if rx.search(words):
            return name
    return None


def summary(text: str) -> str:
    """The report's first line, skipping headings and the status line."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    body = [ln for ln in lines if not ln.startswith("#") and not STATUS_RE.match(ln)]
    return body[0] if body else (lines[0].lstrip("#").strip() if lines else "")


CHANNEL_RE = re.compile(r'^\s*<channel source="([^"]*)"[^>]*>\s*(.*?)\s*</channel>\s*$', re.S)
OWN_CHANNEL = "plugin:build-my-app:"


def rel(path: str, root: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(root.resolve()))
    except Exception:
        return Path(path).name or path


def describe(tool: str, ti: dict, root: Path) -> str:
    """A few words a person would say about this tool call."""
    fp = ti.get("file_path") or ti.get("notebook_path") or ti.get("path") or ""
    if tool == "Read":
        return f"Reading {rel(fp, root)}"
    if tool in ("Edit", "MultiEdit", "NotebookEdit"):
        return f"Editing {rel(fp, root)}"
    if tool == "Write":
        return f"Writing {rel(fp, root)}"
    if tool == "Bash":
        cmd = ti.get("command") or ""
        if "bma_heavy.py" in cmd:
            m = LABEL_RE.search(cmd)
            return f"Running a heavy job{f' for {m.group(1)}' if m else ''}"
        if "spec_lint.py" in cmd:
            return "Linting the specs"
        if "spec_query.py" in cmd:
            return "Looking up specs"
        if "bma_state.py" in cmd:
            return "Updating the workflow state"
        if ti.get("description"):
            return clip(ti["description"], 80)
        return "Running a shell command"
    if tool == "Grep":
        return f"Searching the code for “{clip(ti.get('pattern'), 40)}”"
    if tool == "Glob":
        return f"Looking for files: {clip(ti.get('pattern'), 40)}"
    if tool == "WebSearch":
        return f"Searching the web: {clip(ti.get('query'), 60)}"
    if tool == "WebFetch":
        host = re.sub(r"^https?://([^/]+).*$", r"\1", ti.get("url") or "")
        return f"Reading {host or 'a web page'}"
    if tool in AGENT_TOOLS:
        who = (ti.get("subagent_type") or "an agent").split(":")[-1]
        return f"Asking {who} to {lower_first(clip(ti.get('description'), 60)) or 'help'}"
    if tool == "Skill":
        return f"Loading the {str(ti.get('skill') or '').split(':')[-1]} skill"
    if tool in ("TodoWrite", "TaskCreate", "TaskUpdate"):
        return "Updating the task list"
    if tool == "AskUserQuestion":
        return "Asking you a question in the terminal"
    if tool.startswith("mcp__"):
        parts = tool.split("__")
        return f"Using {parts[1] if len(parts) > 1 else 'a connector'}"
    return f"Using {tool}"


def build(data: dict, root: Path) -> dict | None:
    ev = data.get("hook_event_name") or ""
    base = {"agent": data.get("agent_id"), "type": data.get("agent_type"), "session": data.get("session_id")}
    if ev == "SubagentStart":
        return {**base, "ev": "agent_start"}
    if ev == "SubagentStop":
        report = str(data.get("last_assistant_message") or "")
        return {**base, "ev": "agent_stop", "text": clip(summary(report), 200),
                "outcome": outcome(report) if report.strip() else None, "reported": bool(report.strip())}
    if ev == "PreToolUse":
        tool = data.get("tool_name") or ""
        ti = data.get("tool_input") or {}
        out = {**base, "ev": "tool", "tool": tool, "text": describe(tool, ti, root), "id": data.get("tool_use_id")}
        if tool in AGENT_TOOLS:
            out.update(ev="spawn", spawn_type=ti.get("subagent_type") or "general-purpose",
                       desc=clip(ti.get("description"), 80))
        if tool == "Bash":
            m = LABEL_RE.search(ti.get("command") or "")
            if m:
                out["label"] = m.group(1)
        return out
    if ev == "PostToolUse" and data.get("tool_name") in AGENT_TOOLS:
        tr = data.get("tool_response") or {}
        tr = tr if isinstance(tr, dict) else {}
        return {**base, "ev": "spawned", "id": data.get("tool_use_id"), "child": tr.get("agentId"),
                "status": tr.get("status")}
    if ev == "PostToolUse" and data.get("tool_name") == "AskUserQuestion":
        return {**base, "ev": "question_answered", "tool_use_id": data.get("tool_use_id")}
    if ev == "PostToolUse":
        # Only while the page shows an approval card: tells it the prompt was answered (in the terminal).
        if not (ui_dir(root) / "perm_open").exists():
            return None
        ti = data.get("tool_input") or {}
        sig = ti.get("command") or ti.get("file_path") or json.dumps(ti, ensure_ascii=False)
        return {**base, "ev": "tool_done", "tool": data.get("tool_name"), "sig": clip(str(sig), 160)}
    if ev == "UserPromptSubmit":
        prompt = data.get("prompt") or ""
        m = CHANNEL_RE.match(prompt)
        if m and m.group(1).startswith(OWN_CHANNEL):
            return None  # typed in the web page: the server already recorded it
        if m:  # another channel (Telegram, Discord...): show its text, labeled by source
            return {**base, "ev": "prompt", "via": m.group(1).split(":")[-1] or "channel",
                    "text": clip_text(m.group(2), 1200)}
        return {**base, "ev": "prompt", "via": "terminal", "text": clip_text(prompt, 1200)}
    if ev == "Stop":
        return {**base, "ev": "reply", "text": clip_text(data.get("last_assistant_message"), 2000)}
    return None


def main() -> None:
    data = read_input()
    root = project_dir(data)
    if not is_bma_project(root) or not ui_enabled(root):
        return
    event = build(data, root)
    if event:
        append(root, event)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
