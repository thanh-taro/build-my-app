---
description: Request a change (feature, behavior, design, fix) — it goes through the spec first, then impact analysis, review, and a targeted rebuild.
argument-hint: "<what you want changed>"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_state.py *), Bash(python3 tools/spec_lint.py *), Bash(python3 tools/spec_query.py *)
---

Change request: `$ARGUMENTS`

Load **core**, then the **iterate** skill, and run its change-request procedure:
spec change first → impact analysis (`spec_query.py refs`) → spec review loop → user approval
(per autonomy) → regenerate only the affected design/code/tests → verify → changelog.
