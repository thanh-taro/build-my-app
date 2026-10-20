# build-my-app

A Claude Code plugin (in the **taro-tools** marketplace): a workflow that builds an app from
idea to release with **spec-as-source**, review→fix loops, audits, spikes, and human gates.

```
/build-my-app:start  [idea]
```

## Phases

| # | Phase | Skill | Gate |
|---|---|---|---|
| 0 | Setup & discovery | `setup` | toolchain + profile recorded |
| 1 | Product & spec | `product-spec` | specs reviewed, lint clean, user marks `ready` |
| 2 | Design | `design` | all M-1 states designed, audited, approved |
| 3 | Architecture & spikes | `architecture`, `spike-resolver` | shell builds, CI green, spikes closed |
| 4 | Implementation | `build` | features shipped, AC coverage 100% |
| 5 | QA & hardening | `qa` | traceability matrix passing, audits clean |
| 6 | Release | `release` | user submits/publishes |
| 7 | Iterate | `iterate` | per change request |

Phases 2 and 3 run in parallel after gate 1. Shared rules live in the `core` skill
(decision policy, gates, review loops, escalation, autonomy).

## Commands

| Command | Purpose |
|---|---|
| `/build-my-app:start [idea]` | Start or resume |
| `/build-my-app:status` | Progress, gates, open decisions |
| `/build-my-app:decide` | Answer pending decisions |
| `/build-my-app:change <request>` | Change request → spec → targeted rebuild |
| `/build-my-app:spike <question>` | Time-boxed technical spike → ADR |
| `/build-my-app:autonomy [level]` | guided · balanced · autopilot |
| `/build-my-app:audit <kind> [scope]` | Re-run audits (spec, design, code, qa, license, a11y, security, perf) |

Want plain `/build-my-app`? Copy `extras/build-my-app.alias.md` to
`~/.claude/commands/build-my-app.md`.

## Components

- **Skills**: `core`, one per phase (`setup` … `iterate`), `spike-resolver`,
  spec tools (`spec-context`, `spec-author`, `spec-derive`), stack packs
  (`stack-ios`, `stack-web`, `stack-android`, `stack-backend`).
- **Agents**: product-strategist, market-researcher, spec-reviewer, design-auditor,
  ui-critic, architect, license-auditor, spike-runner, feature-builder, code-reviewer,
  security-auditor, a11y-auditor, perf-analyst, qa-runner, stuck-resolver, release-manager.
- **Hooks** (no-ops outside build-my-app projects): session orientation, spec-ID context
  injection, state/generated-file edit guard, destructive-command and unregistered-dependency
  guard, spec lint after spec edits, compaction log, pause notice on stop.
- **Scripts**: `scripts/bma_state.py` (workflow state machine, stored in
  `.build-my-app/state.json` in the project).
- **Project template** (`templates/project/`): spec tree with templates and rules, spec lint
  and query tools (vendored into the project so CI can run them), `CLAUDE.md`.

## Install

From GitHub:
```
/plugin marketplace add thanh-taro/build-my-app
/plugin install build-my-app@taro-tools
```

From a local clone:
```
claude plugin validate /path/to/build-my-app
/plugin marketplace add /path/to/build-my-app
/plugin install build-my-app@taro-tools
```
Run `/reload-plugins` after editing the plugin.

## Status

v0.1.0 — skeleton. Phases 0–1 and the core protocols are fully specified; phases 2–7 have
complete step lists but are untested end to end. See `ROADMAP.md`.

## License

Source-available, **not open source**. You may read the code and use the plugin for
personal, non-commercial purposes. Copying, redistributing, publishing modified versions,
and any commercial use are not allowed without written permission. See [LICENSE](LICENSE).
