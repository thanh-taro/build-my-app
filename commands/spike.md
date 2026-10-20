---
description: Run a time-boxed technical spike to resolve a feasibility or performance unknown, ending in an ADR.
argument-hint: "<question to answer, e.g. 'can one compositor drive preview and export at 30 fps?'>"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_state.py *), Bash(python3 tools/spec_query.py *)
---

Spike question: `$ARGUMENTS`

Load **core**, then the **spike-resolver** skill, and run it for this question.
