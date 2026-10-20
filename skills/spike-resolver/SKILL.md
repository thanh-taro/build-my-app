---
name: spike-resolver
description: Run a time-boxed technical spike in an isolated git worktree to answer one feasibility or performance question, measure the result, and record the outcome as an ADR. Use for risky unknowns in architecture, or when implementation is stuck on something that may not be feasible.
---

# Spike resolver

Follow **core**.

1. **Frame it** — write `.build-my-app/reports/spike-<slug>.md`:
   question; hypothesis; success measure (numbers, e.g. "≥ 30 fps at 1080p on the reference
   device"); time box (e.g. ≤ 2 hours of agent work / N turns); what will NOT be built.
2. **Isolate** — run the `spike-runner` agent with `isolation: worktree` (or create a
   worktree `spike/<slug>` yourself). Spike code never lands on the main branch by accident.
3. **Build the smallest thing** that can answer the question; instrument it.
4. **Measure** against the success measure; capture evidence (numbers, logs, screenshots).
5. **Decide** — one of: adopt (approach works), adapt (works with changes), reject (change
   spec or architecture). Record an ADR; if specs must change, use the spec-author skill and
   the review loop.
6. **Clean up** — delete the worktree, or promote specific code deliberately (separate commit
   that references the ADR).
7. If the time box ends without an answer → escalation protocol (ask the user whether to
   extend, change approach, or change the spec).
