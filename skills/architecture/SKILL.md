---
name: architecture
description: Phase 3 of build-my-app — choose the stack with ADRs, audit licenses, design modules, map neutral spec wording to platform APIs, resolve risky unknowns with spikes, and scaffold the project with CI and code generation. Use when the workflow is in the architecture phase.
---

# Phase 3 — Architecture, foundations & spikes

Follow **core**. Load the matching stack pack skill (`stack-ios`, `stack-web`,
`stack-android`, `stack-backend`) for platform specifics.

## 3.1 Architecture (with the `architect` agent)
1. Stack choice with alternatives → one ADR per significant decision in
   `specs/40-technical/adr/` (from `specs/_templates/adr.md`).
2. Dependency & asset policy ADR (allowed licenses, banned licenses, asset rules) and the
   registry `specs/40-technical/dependencies.md`. Run the `license-auditor` agent on every
   candidate before it is approved.
3. Modules: one file per module in `specs/40-technical/modules/` (responsibility, boundaries,
   public surface, which features it implements).
4. `specs/40-technical/architecture.md` (overview diagram, data flow, baselines) and
   `platform-mapping.md` (neutral spec wording → platform APIs).

## 3.2 Spikes
For each spike candidate recorded in phase 1 (`bma_state.py get spike_candidates`) and any new
unknown: run the **spike-resolver** skill. Spikes that change the plan update specs/ADRs first.

## 3.3 Foundations
1. Scaffold the project per the stack pack (module structure from 3.1).
2. Code generation from specs (per `adapters/codegen.md`): data model types from the schema,
   design token constants, string catalog from `copy.md`, acknowledgements from the registry.
3. Test harness + fixtures; tests named per `adapters/tests.md`.
4. CI: build, unit tests, `python3 tools/spec_lint.py`, license scan, (coverage report).

## Gate G3
Automated: the empty app shell builds and runs; CI green; all spikes closed with ADRs; every
dependency `approved`. Approval: user approves the stack and any decision of kind money/legal.
Then `bma_state.py gate architecture pass`.
