---
name: spec-context
description: Find and load the exact spec content needed for a task — by spec ID (F-003, SCR-Editor, RULE-04…) or by topic. Use before answering questions about app behavior, designing, implementing, testing, or reviewing, and whenever a prompt mentions a spec ID, in projects that have specs/ and tools/spec_query.py.
---

# Spec context

`specs/` is the single source of truth. Extract it with `tools/spec_query.py`:

| You have | Run |
|---|---|
| An ID, need everything to work on it | `python3 tools/spec_query.py context <ID>` |
| …with linked screens/features in full | `python3 tools/spec_query.py context <ID> --full` |
| Exact definitions | `python3 tools/spec_query.py show RULE-04 INV-03 F-008.R5` |
| A topic, no ID | `python3 tools/spec_query.py search "<regex>"` → then `show`/`context` the owners |
| A scope | `python3 tools/spec_query.py list F --milestone M-1` / `list F --status ready` |
| Impact of a change | `python3 tools/spec_query.py refs <ID>` |

Rules: load the smallest sufficient context; quote IDs in answers; if specs do not answer the
question, say so and offer a spec change (spec-author); mention `draft` status when it matters.
