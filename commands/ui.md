---
description: Open the build-my-app web UI — a live room of the agents at work, the conversation, and the progress panel.
argument-hint: "[stop|status]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_ui.py *)
---

Argument: `$ARGUMENTS`

- `stop` → run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_ui.py stop` and report the result.
- `status` → run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_ui.py status` and report it.
- anything else, or empty → run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_ui.py start --open`.

After `start`, reply in at most four lines: the URL exactly as printed (it carries the access
token, so it must be copied whole), that the page updates live, and that this version only
watches: the user keeps typing in the terminal, and their messages and your replies show up
in the page's front desk. Mention `/build-my-app:ui stop` to close it. Do not start other work.
