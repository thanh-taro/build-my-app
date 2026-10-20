---
name: design
description: Phase 2 of build-my-app — build the app's style with the user (style tile, design tokens), choose and set up the design tool, plan the design in phases, and run the make → spec audit → UI/UX critique → fix loop until the user approves. Use when the workflow is in the design phase.
---

# Phase 2 — Design

Follow **core**. Inputs: `ready` specs — screens, components, flows, copy, tokens.
Use `python3 tools/spec_query.py context <SCR-/CMP-/FLOW- ID> --full` as the brief for every
screen or component.

Steps (each in its own file — read it when you reach the step):
1. **Style builder** — `${CLAUDE_SKILL_DIR}/steps/1-style-builder.md`
2. **Tool selection & setup** — `${CLAUDE_SKILL_DIR}/steps/2-tool-setup.md`
3. **Design plan** — `${CLAUDE_SKILL_DIR}/steps/3-plan.md`
4. **Design loop** (per design phase) — `${CLAUDE_SKILL_DIR}/steps/4-design-loop.md`

## Gate G2
Automated: every screen state and component variant in M-1 specs has a design; design
auditor reports no blockers; every text uses a COPY ID; only tokens are used; contrast and
touch-target checks pass; the design adapter (`adapters/design.md`) matches the chosen tool.
Approval: the user approves the designs (decision kind: design). Then
`bma_state.py gate design pass`.
