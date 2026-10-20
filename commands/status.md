---
description: Show build-my-app progress — phases, gates, current step, open decisions, active loops.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_state.py *), Bash(python3 tools/spec_lint.py *), Bash(python3 tools/spec_query.py *)
---

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_state.py status` and
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_state.py next`.
If `specs/` exists, also run `python3 tools/spec_lint.py | tail -1` and
`python3 tools/spec_query.py list F` to count features by status.

Report in under 15 lines: where we are, what is next, what is waiting on the user, and the
spec health line. Do not start any work.
