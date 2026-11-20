---
description: Open the build-my-app web UI — chat with Claude, watch the agents at work in a live room, and follow progress.
argument-hint: "[stop|status]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_ui.py *)
---

Argument: `$ARGUMENTS`

- `stop` → run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_ui.py stop` and report the result.
- `status` → run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_ui.py status` and report it.
- anything else, or empty → run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_ui.py start --open`.

After `start`, reply in at most five lines:
- the URL exactly as printed (it carries the access token, so copy it whole);
- whether chat is on, as the command printed. If it printed the restart command, show it in a
  code block and say the page still works as a live view without it;
- `/build-my-app:ui stop` closes it.

Messages typed in the page arrive in this session as channel events from the same user:
handle them exactly like terminal messages. Do not start other work now.
