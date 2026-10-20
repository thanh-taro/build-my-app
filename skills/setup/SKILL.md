---
name: setup
description: Phase 0 of build-my-app — profile the user, inspect the environment and toolchains, initialize git, workflow state, spec tooling, and project instructions. Use when /build-my-app:start runs in a project without workflow state.
---

# Phase 0 — Setup & discovery

Follow **core**. State CLI: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_state.py`.

## Steps
1. **Initialize state**: `bma_state.py init` then `bma_state.py phase setup in_progress`.
2. **Inspect the folder.**
   - Empty or near-empty → greenfield.
   - Existing code without `specs/` → brownfield: tell the user phase 1 will start with a
     *reverse spec* (derive specs from the code) and confirm before continuing.
   - Existing `specs/` → reuse them; run the lint to see their health.
3. **Profile the user** (one AskUserQuestion round, ≤ 4 questions):
   - goal: personal / side project / startup / client work;
   - experience: non-developer / developer new to the platform / experienced;
   - budget for paid services and assets (none / small / flexible);
   - autonomy level (guided / balanced (Recommended) / autopilot).
   Save: `bma_state.py set profile '<json>'`, `bma_state.py set autonomy <level>`.
4. **Check the environment** (report, do not install anything without asking):
   git; language runtimes; platform toolchains already present (e.g. `xcodebuild -version`,
   `xcrun simctl list`, `node -v`, Android SDK); available connectors/MCP tools (design tools,
   GitHub, browser automation). Record findings with `bma_state.py set environment '<json>'`.
5. **Initialize the project** (ask before creating files in a non-empty folder):
   - `git init` if needed (no commits yet).
   - Copy the project template: `cp -R ${CLAUDE_PLUGIN_ROOT}/templates/project/tools ./tools`,
     `cp -R ${CLAUDE_PLUGIN_ROOT}/templates/project/specs ./specs` (skip files that exist),
     `CLAUDE.md` from the template (fill `{{APP_NAME}}` / `{{ONE_LINE_PITCH}}` later in phase 1),
     and `.gitignore` from `templates/project/gitignore` (merge if one exists).
   - Create `.build-my-app/reports/`.
   - Run `python3 tools/spec_lint.py` (an empty spec tree is fine).
6. **Gate G0** (gate protocol): checks — state file exists, git repo exists, `tools/` runs,
   profile and autonomy recorded. Approval: show the summary; on approval
   `bma_state.py gate setup pass`. Then continue with phase 1 (product-spec).
