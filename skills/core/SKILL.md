---
name: core
description: Core protocols of the build-my-app workflow — state handling, autonomy levels, decision policy, gates, review→fix loops, escalation, and cost control. Load before running any build-my-app phase, and whenever a build-my-app skill says "follow core".
---

# build-my-app core

Every phase skill follows these rules. The state CLI is the single place progress is recorded:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_state.py <command>
```
(`status`, `next`, `phase`, `step`, `gate`, `decide`, `loop`, `set`, `get`, `log` — see `--help`.)

## Non-negotiables
1. **Spec is the source of truth.** Read with `python3 tools/spec_query.py`, validate with
   `python3 tools/spec_lint.py`. Never generate designs/code from specs that are not `ready`.
2. **Record progress as you go.** Update `step` at each meaningful step and `log` notable
   events, so the run can resume after a session ends or context is compacted.
3. **Never pass a gate silently.** Follow `${CLAUDE_SKILL_DIR}/protocols/gates.md`.
4. **Ask or decide per the decision policy** in `${CLAUDE_SKILL_DIR}/protocols/decisions.md`.
5. **Loops converge.** Review→fix cycles follow `${CLAUDE_SKILL_DIR}/protocols/review-loop.md`.
6. **Escalate when stuck.** Follow `${CLAUDE_SKILL_DIR}/protocols/escalation.md`.
7. **Hard stops — always the user's call, at every autonomy level:** spending money, creating
   accounts, entering credentials or secrets, legal/licensing choices, sending data off-device,
   publishing or submitting anything, deleting user data, force-pushing.

## Autonomy levels (`bma_state.py get autonomy`)
| Level | Ask the user for |
|---|---|
| guided | every phase output and every non-trivial decision |
| balanced | gates; product, design-direction, money, legal, release decisions |
| autopilot | hard stops only (rule 7); gates auto-pass when all automated checks pass, and the user gets a summary |

## Communication
- Keep the user oriented: one line when a step starts ("Phase 2 · design audit, round 2/3").
- Findings and long outputs go into files under `.build-my-app/reports/`; chat gets the summary.
- When asking, give a recommendation first, the options, and what changes with each.

## Cost control
- Use the cheapest capable model per job: mechanical checks (lint, formatting, scans) on
  small/fast agents; reviews, architecture, and design critique on the strongest model.
- Fan out in parallel only where work is independent (feature groups, screens, audits).
- Before a phase expected to be large, tell the user the rough scale (number of agents/rounds).
