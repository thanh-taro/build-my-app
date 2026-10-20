---
name: build
description: Phase 4 of build-my-app — implement ready features in dependency order through a test-first pipeline (context → tests from acceptance criteria → implement → verify by running the app → code review + spec audit → fix → commit), in parallel worktrees where independent. Use when the workflow is in the build phase.
---

# Phase 4 — Implementation

Follow **core**. Load the stack pack skill and the **spec-context** skill.

## Plan
1. Features for the milestone: `python3 tools/spec_query.py list F --milestone M-1 --status ready`.
2. Order by `depends_on`; group independent features into waves that can run in parallel.
3. Write `.build-my-app/reports/build-plan.md`; show it (guided/balanced) before starting.

## Feature pipeline (one `feature-builder` agent per feature; parallel waves use
## `isolation: worktree`)
1. **Context**: `spec_query.py context F-xxx --full` + linked designs (via the design adapter).
2. **Tests first**: one or more tests per AC, named per `adapters/tests.md`; unit tests for
   every RULE/INV touched. Confirm they fail for the right reason.
3. **Implement** respecting ADRs and module boundaries; cite IDs (`// Implements: F-xxx.R#`);
   strings via COPY IDs only; design values via tokens only; new dependencies must be
   `approved` in the registry.
4. **Verify**: build; all tests; `spec_lint.py`; **run the app** and capture screenshots of the
   feature's screens/states; compare with the designs.
5. **Review** (review-loop protocol, loop `build-F-xxx`):
   `code-reviewer` (bugs, simplicity) + spec audit (every R implemented, every AC tested:
   `spec_lint.py --coverage <tests-dir>`) + `security-auditor` when the feature touches data,
   network, files, auth, or payments.
6. **Commit / PR** referencing the spec IDs; set the feature `status: building`, then
   `shipped` when merged (update `_index.md`; changelog if behavior changed).

## Guards
- **Spec drift**: implementation reveals a gap → stop that feature, propose a spec change
  (spec-author), review it, then continue.
- **Stuck**: escalation protocol after 2–3 genuine attempts; consider a spike.
- **Merge waves** one feature at a time; re-run the full test suite after each merge.

## Gate (per milestone)
Automated: all milestone features `shipped`; CI green; AC coverage 100% (or each gap listed
as a recorded manual check). Approval per autonomy. Then `bma_state.py gate build pass`.
