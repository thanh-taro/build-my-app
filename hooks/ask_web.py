#!/usr/bin/env python3
"""PreToolUse (AskUserQuestion): let the user answer Claude's question in the web UI.

Only when the web page is open and was visible in the last minute; otherwise the question opens
in the terminal as usual, and the page shows it as "waiting in the terminal" (read-only) so it
never misses one. While the page has the question, the
terminal shows no dialog (a hook runs before it), so the wait ends when:
  - the user answers in the page → the hook returns the answers and the tool runs without a dialog;
  - the user clicks "Answer in the terminal", closes the page, or WAIT_MAX passes → the hook
    returns nothing and the normal terminal dialog opens.
Fails open: any error also falls back to the terminal.
"""
from __future__ import annotations

import json
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from _common import emit, is_bma_project, project_dir, read_input  # noqa: E402
from bma_events import append, ui_dir, ui_enabled  # noqa: E402

WAIT_MAX = 300        # seconds; hooks.json gives this hook a longer timeout
VISIBLE_WITHIN = 60   # the page must have been visible this recently to take a question
PAGE_GONE_AFTER = 45  # no word from any open page for this long → back to the terminal
POLL = 0.3


def presence(root: Path) -> dict:
    try:
        return json.loads((ui_dir(root) / "presence.json").read_text())
    except Exception:
        return {}


def main() -> None:
    data = read_input()
    root = project_dir(data)
    if data.get("tool_name") != "AskUserQuestion" or not is_bma_project(root) or not ui_enabled(root):
        return
    ti = data.get("tool_input") or {}
    questions = ti.get("questions") or []
    if not questions or ti.get("answers"):
        return
    tid = data.get("tool_use_id")
    if time.time() - presence(root).get("visible", 0) > VISIBLE_WITHIN:
        append(root, {"ev": "question", "qid": "q" + secrets.token_hex(4), "questions": questions,
                      "agent": data.get("agent_id"), "tool_use_id": tid, "where": "terminal"})
        return
    qid = "q" + secrets.token_hex(4)
    answer_file = ui_dir(root) / "answers" / f"{qid}.json"
    answer_file.parent.mkdir(parents=True, exist_ok=True)
    append(root, {"ev": "question", "qid": qid, "questions": questions, "agent": data.get("agent_id"), "tool_use_id": tid})
    end = time.time() + WAIT_MAX
    reason = "timeout"
    while time.time() < end:
        if answer_file.exists():
            try:
                ans = json.loads(answer_file.read_text())
            except ValueError:
                time.sleep(POLL)  # half-written; the server writes atomically, but be safe
                continue
            answer_file.unlink(missing_ok=True)
            if ans.get("terminal"):
                reason = "terminal"
                break
            answers = {str(k): str(v) for k, v in (ans.get("answers") or {}).items()}
            if not all(q.get("question") in answers for q in questions):
                reason = "incomplete"
                break
            append(root, {"ev": "question_done", "qid": qid, "via": "web"})
            emit({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "Answered in the build-my-app web page.",
                "updatedInput": {**ti, "answers": answers},
            }})
            return
        if not ui_enabled(root) or time.time() - presence(root).get("seen", 0) > PAGE_GONE_AFTER:
            reason = "page closed"
            break
        time.sleep(POLL)
    append(root, {"ev": "question_done", "qid": qid, "via": "terminal", "reason": reason})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
