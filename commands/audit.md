---
description: Re-run the audits of a build-my-app phase on demand (spec, design, code, qa, license, a11y, security, perf).
argument-hint: "<spec|design|code|qa|license|a11y|security|perf> [IDs or paths]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_state.py *), Bash(python3 tools/spec_lint.py *), Bash(python3 tools/spec_query.py *)
---

Audit request: `$ARGUMENTS`

Load **core**. Run the matching reviewer agent(s) on the given scope (default: everything
changed since the last gate), using the review-loop protocol but **report only** — do not fix
unless the user asks. Agents: spec → spec-reviewer · design → design-auditor + ui-critic ·
code → code-reviewer · qa → qa-runner · license → license-auditor · a11y → a11y-auditor ·
security → security-auditor · perf → perf-analyst.
Write the merged report to `.build-my-app/reports/audit-<kind>-<date>.md` and summarize.
