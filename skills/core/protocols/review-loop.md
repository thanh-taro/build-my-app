# Review → fix loop protocol

Used for spec reviews, design audits, code reviews, and QA audits.

1. `bma_state.py loop start <name> --max 3`.
2. **Review** — run the relevant reviewer agents (in parallel when scopes are independent).
   Give each a precise scope, the decisions already in force (so they do not re-litigate),
   and the bar: "only what causes a wrong design, wrong implementation, or untestable
   criterion; no nitpicks".
3. **Merge** — deduplicate findings across reviewers; issues found independently by several
   reviewers are high-confidence. Write `.build-my-app/reports/<name>-round-<n>.md`.
4. **Triage** each finding:
   - clear fix → apply it;
   - needs a decision → decision protocol (batch the questions);
   - disagree → note why in the report (no silent drops).
5. **Fix**, then run the mechanical checks (lint, build, tests).
6. **Re-review only what changed**, plus anything those changes reference (`spec_query.py refs`).
   `bma_state.py loop next <name>` — exit code 3 means the round limit was reached.
7. **Stop** when there are no blockers or majors left: `loop end <name> --outcome converged`.
   At the limit with blockers remaining: escalate (escalation protocol) with the remaining
   list; never loop past the limit without the user's consent.
