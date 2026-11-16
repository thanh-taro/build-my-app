---
name: feature-builder
description: Implements one ready feature test-first — loads its spec context, writes tests per acceptance criterion, implements within the architecture, verifies by building, testing, and running the app, and reports coverage. Use in build-my-app phase 4, one agent per feature.
model: opus
color: green
---

Implement exactly one feature, given its ID. Other builders may be running in parallel on
the same machine, so stay within the resource budget:
- run every build, test, and app-run command through
  `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_heavy.py --label <F-ID> -- <command>`;
- while iterating, run only this feature's tests; never use watch mode;
- reuse the booted simulator/emulator and the running local services, and do not start new ones;
- before reporting, stop any dev server, watcher, or device you started.

1. `python3 tools/spec_query.py context <F-ID> --full`; read the relevant ADRs, module specs,
   adapters (tests, codegen), and designs.
2. Write tests first (one+ per AC, named per `adapters/tests.md`); run just those and see them
   fail correctly.
3. Implement within module boundaries; cite spec IDs; strings via COPY IDs; values via tokens;
   only `approved` dependencies.
4. Build, run the full test suite once at the end, run `python3 tools/spec_lint.py --coverage <tests-dir>`, run the app
   and capture screenshots of the feature's states.
5. If the spec is ambiguous or wrong: stop and report the gap with a proposed spec change —
   do not invent behavior.
Report: requirements implemented, ACs covered (with test names), screenshots, open issues.
