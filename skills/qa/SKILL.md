---
name: qa
description: Phase 5 of build-my-app — end-to-end flow tests, visual regression against designs, NFR measurement, accessibility, security/privacy, and license audits, with a bug triage loop and a traceability matrix. Use when the workflow is in the QA phase.
---

# Phase 5 — QA & hardening

Follow **core**. Run audits in parallel where independent (agents: `qa-runner`,
`a11y-auditor`, `security-auditor`, `perf-analyst`, `license-auditor`).

1. **Flows**: one end-to-end UI test per `FLOW-` spec; run on the stack's simulator/emulator
   or browser.
2. **Visual regression**: screenshots of every designed state vs. approved designs; report
   differences beyond the agreed tolerance.
3. **NFRs**: measure each `NFR-` with the method in `specs/50-quality/nfr.md`; anything only
   measurable on real devices → a manual checklist item for the user.
4. **Accessibility**: labels, contrast, touch targets, screen-reader pass, larger text sizes.
5. **Security & privacy**: data storage, network, permissions, secrets in code, third-party
   SDK data collection; draft store privacy declarations.
6. **Licenses**: every dependency/asset `approved`; nothing `personal-only` in release builds.
7. **Bug triage loop**: reproduce → failing test → fix → full suite; spec gaps go through the
   spec-author skill.
8. **Traceability matrix**: `.build-my-app/reports/traceability.md` — every AC → test(s) →
   last result; every NFR → measurement → result.

## Gate G5
Automated: matrix 100% passing (manual items signed off by the user); audits without
blockers. Approval per autonomy. Then `bma_state.py gate qa pass`.
