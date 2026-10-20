---
name: spec-derive
description: Generate derived artifacts from specs — user stories/tickets, design briefs, test plans, release notes — following the project's adapters. Use when asked for stories, a design brief, a test plan, or release notes for spec IDs or a milestone.
---

# Derive artifacts from specs

Derived artifacts are disposable: specs never change to match them. Gaps found while deriving
are reported (and offered to spec-author), not filled in the artifact. Use `ready` specs
unless the user allows drafts (then label the output "DRAFT").

- **stories** (`adapters/tracker.md`): one epic per feature (`F-xxx <title>`, intent + scope +
  spec path); stories grouped by requirements ("As PER-xx, I can … so that …") with their
  ACs verbatim as the checklist; NFR IDs as quality items; order by `depends_on`.
- **design-brief** (`adapters/design.md`): purpose, every state/variant to design with frame
  names, components, all COPY strings, tokens, accessibility notes, behaviors affecting layout.
- **test-plan** (`adapters/tests.md`): AC → level → test name → fixtures; plus RULE/INV unit
  tests and NFR checks.
- **release-notes**: shipped features + changelog, plain user language, glossary terms, no IDs
  in user-facing text (IDs in an internal appendix).

Always list the spec IDs the artifact was derived from.
