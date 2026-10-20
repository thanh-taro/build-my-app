# Escalation protocol (stuck resolver)

Trigger: the same problem resists **2–3 genuine attempts** (build error, failing test,
unmet performance target, reviewer blocker that keeps coming back), or a step needs something
only the user can provide.

1. **Stop retrying the same approach.** Write down: goal, what was tried, exact errors/evidence.
2. **Diagnose** with the `stuck-resolver` agent (fresh eyes; give it the write-up, not the
   whole history).
3. **Try one different approach** it proposes. If the unknown is about feasibility or
   performance, run a **spike** (`/build-my-app:spike`) instead of more attempts in the main line.
4. Still stuck → **ask the user** with: the goal, a 3-line summary of attempts, the options
   (e.g. change the spec, accept a limitation, provide access/info, pause), and a recommendation.
5. Record the outcome (ADR, spec change, or known limitation) and continue.
