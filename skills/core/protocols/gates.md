# Gate protocol

Each phase ends at a gate. A gate has **automated checks** and an **approval**.

1. Set the phase to `gate`: `bma_state.py phase <id> gate`.
2. Run every automated check listed in the phase skill's gate section. Record results in
   `.build-my-app/reports/gate-<phase>.md` (check, result, evidence).
3. If any check fails → fix (review-loop protocol) and re-run; do not ask for approval yet.
4. Approval:
   - guided / balanced: present a short gate summary (what was produced, checks, choices made,
     open risks) and ask the user to approve, request changes, or stop.
   - autopilot: auto-approve when all checks pass; show the summary.
5. On approval: `bma_state.py gate <id> pass --note "<summary>"`. On change requests: apply
   them, then repeat from step 2.
6. Never start a phase whose prerequisites' gates have not passed (the state CLI enforces it).
