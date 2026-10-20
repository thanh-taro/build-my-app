---
description: Show or change how much build-my-app asks before acting (guided, balanced, autopilot).
argument-hint: "[guided|balanced|autopilot]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_state.py *)
---

Requested level: `$ARGUMENTS`

- No argument → show the current level (`bma_state.py get autonomy`) and explain the three
  levels in one line each (see the core skill).
- With a level → `bma_state.py set autonomy <level>` and confirm. Remind the user that hard
  stops (money, credentials, legal, publishing, data leaving the device) always ask.
