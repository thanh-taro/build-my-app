---
name: deploy
description: Phase 7 of build-my-app — ship the approved release candidate off the machine. Provision environments (user-owned), deploy the exact candidate to staging or a beta track, verify, promote to production or submit to the stores, verify again, and roll back if needed. Use when the workflow is in the deploy phase.
---

# Phase 7 — Deploy

Follow **core**. Load the stack pack for the release channel. Use the `release-manager`
agent for the checklist and `qa-runner` for checks against deployed environments.
Every step that touches the outside world is a **hard stop**: the user performs it, or
approves each command before Claude runs it (the bash guard asks every time).

1. **Pre-flight**: gate G6 passed; `HEAD` is the approved candidate tag (otherwise go back to
   phase 6 for a new candidate); runbook and environment inventory are current.
2. **Provision** (user-owned): accounts, billing, domains, hosting projects, store records,
   and secrets set in the provider — from `docs/deploy/environments.md`. Claude may apply
   infrastructure definitions only after the user approves the plan output.
3. **Staging / beta**: deploy the candidate artifact — web/backend to staging; iOS to
   TestFlight internal; Android to the internal testing track. Run data migrations per the
   runbook. Then run the smoke checks and the `FLOW-` tests against staging (qa-runner);
   check logs and error reports. Failures → stop, roll back staging, fix through phases 4–6
   (bug → failing test → fix → new candidate).
4. **Promote** (decision kind: release, always the user): production deploy or store
   submission with the **same artifact** that passed staging — never rebuild in between.
   Store submissions are done by the user with the exact steps from the runbook.
5. **Post-deploy verification**: smoke checks against production; watch errors, crash rate,
   and key metrics for the window agreed in the runbook. On a failed check, follow the
   rollback plan immediately and tell the user.
6. **Record**: tag the final version `vX.Y.Z`; write
   `.build-my-app/reports/deploy-<version>.md` (what went where, when, checks, issues);
   add the release date to `specs/60-delivery/changelog.md`; publish the release notes where
   the channel needs them.

## Gate G7
Automated: production (or the store release) runs the approved candidate; post-deploy checks
pass. Approval: the user confirms the app is live (or approved by the store). Then
`bma_state.py gate deploy pass`.
