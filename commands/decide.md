---
description: Review and answer the open decisions blocking the build-my-app workflow.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_state.py *)
---

Load the **core** skill. List open decisions:
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_state.py decide list --open`.

For each (batch up to 4 per question round), ask the user with the recommended option first.
Record each answer with `decide answer`, apply it where it belongs (spec, ADR, changelog), run
the relevant checks, then tell the user they can continue with `/build-my-app:start`.
