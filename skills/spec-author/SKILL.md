---
name: spec-author
description: Create or change specs (features, screens, components, flows, rules, entities, ADRs, copy, tokens, NFRs) following the spec-as-source conventions, with lint and changelog. Use when adding/modifying behavior, writing phase-1 specs, recording decisions, or when design/implementation reveals a missing or ambiguous spec.
---

# Spec author

Read `specs/README.md` once per session — it is the rulebook (layers, ID scheme, statuses,
definition syntax, formats).

1. **Locate** existing content: `spec_query.py search "<topic>"`, `refs <ID>`. Reuse IDs;
   never duplicate a fact.
2. **Right home** (one fact, one place): limits/defaults → RULE; always-true constraints →
   INV; data → ENT + schema; user capability → feature file from `_templates/feature.md`;
   look & feel → SCR/CMP/FLOW, strings → `copy.md`, values → `tokens.json`; technology
   choices → ADR (accepted ADRs are immutable); quality bar → NFR; events → analytics.
3. **IDs**: next free number (`spec_query.py list RULE`); never renumber, rename, or reuse;
   removal = `deprecated`. Append new R#/AC# at the end of their lists.
4. **Write**: requirements = observable behavior, no UI layout, no implementation, no tool
   names; every requirement covered by ≥ 1 Given/When/Then AC ending with `(R#)`; UX notes
   reference SCR/CMP/COPY IDs only; neutral layers stay tool- and platform-free.
5. **Sync**: `_index.md`, roadmap, and changelog (for `building`/`shipped` items).
6. **Lint**: `python3 tools/spec_lint.py` → 0 errors; treat warnings as todos.
7. **Status**: new items start `draft`; only the user moves items to `ready` (or explicitly
   delegates it).
