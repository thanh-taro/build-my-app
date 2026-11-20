# build-my-app

A Claude Code plugin (in the **taro-tools** marketplace): a workflow that builds an app from
idea to release with **spec-as-source**, review→fix loops, audits, spikes, and human gates.

```
/build-my-app:start  [idea]
```

## Install

**Requirements:** [Claude Code](https://claude.com/claude-code), `git`, and `python3` (3.9+,
standard library only). The toolchain for your target platform (Xcode, Android SDK, Node,
Docker…) is checked in phase 0, and nothing is installed without asking.

### From GitHub (recommended)

Inside Claude Code:
```
/plugin marketplace add thanh-taro/build-my-app
/plugin install build-my-app@taro-tools
/reload-plugins
```

### From a local clone (to read or tweak the plugin)

```bash
git clone https://github.com/thanh-taro/build-my-app.git ~/build-my-app
claude plugin validate ~/build-my-app
```
Then inside Claude Code:
```
/plugin marketplace add ~/build-my-app
/plugin install build-my-app@taro-tools
/reload-plugins
```
Local edits take effect after `/reload-plugins`.

### Check it works

Run `/build-my-app:status` in any folder. Outside a build-my-app project it reports that
there is no state yet. That means the plugin is loaded.

### Optional: plain `/build-my-app`

```bash
mkdir -p ~/.claude/commands
cp ~/build-my-app/extras/build-my-app.alias.md ~/.claude/commands/build-my-app.md
```

### Update or remove

```
/plugin marketplace update taro-tools     # pull the latest version
/plugin uninstall build-my-app@taro-tools
/plugin marketplace remove taro-tools
```

## Example

Start in an empty folder. Each project gets its own folder, and all workflow state lives
inside it, in `.build-my-app/`.

```bash
mkdir ~/apps/habit-streaks && cd ~/apps/habit-streaks
claude
```

```
/build-my-app:start a habit tracker that keeps streaks without guilt-tripping
```

A typical run looks like this (balanced autonomy). ▶ marks where Claude stops and waits
for you.

1. **Setup (0):** Claude asks 4 quick questions (goal, experience, budget, autonomy) and
   checks your toolchains. Then it sets up git, `specs/` and `tools/`.
   ▶ Approve the setup gate.
2. **Product & spec (1):** brainstorming, market research and MVP scope. Specs are written
   to `specs/` (features `F-001…`, screens, flows, rules) and reviewed until lint is clean.
   ▶ You choose the platform (say, iOS) and mark the specs `ready`.
3. **Design (2) and architecture (3), in parallel:** a style tile, then designs per screen
   and state. The stack is recorded as ADRs, risky unknowns go through spikes, and the app
   shell is scaffolded with a **local** environment (`make setup`, `make dev`).
   ▶ Approve the designs and the stack.
4. **Build (4):** one feature at a time, tests first. Each feature is run in the simulator
   against local services and screenshotted next to its design, then reviewed.
5. **QA (5):** end-to-end flows, visual regression, accessibility, security and license
   audits, and a traceability matrix. All of it runs locally.
6. **Release candidate (6):** sets version `1.0.0`, builds and tests the release build
   locally, and writes release notes, store assets, the environment list and the deploy
   guide. It tags `v1.0.0-rc.1`. ▶ Approve the candidate.
7. **Deploy (7):** ▶ You create the accounts, signing and secrets by following the deploy
   guide. The same build goes to TestFlight and is checked there. ▶ You submit it to the
   App Store. Claude then checks production and tags `v1.0.0`.

You can stop at any point. A new session picks up where you left off:

```
/build-my-app:status                      # where are we, what is waiting on me?
/build-my-app:start                       # continue
```

After launch, changes go through the spec first and rebuild only what they affect:

```
/build-my-app:change let users pause a habit for a week without breaking the streak
/build-my-app:spike can the widget refresh streaks within 1 s of a check-in?
/build-my-app:audit a11y SCR-Today
/build-my-app:autonomy autopilot          # fewer questions; hard stops still ask
```

## Phases

| # | Phase | Skill | Gate |
|---|---|---|---|
| 0 | Setup & discovery | `setup` | toolchain + profile recorded |
| 1 | Product & spec | `product-spec` | specs reviewed, lint clean, user marks `ready` |
| 2 | Design | `design` | all M-1 states designed, audited, approved |
| 3 | Architecture & spikes | `architecture`, `spike-resolver` | shell builds, CI green, spikes closed |
| 4 | Implementation (local) | `build` | features shipped, AC coverage 100% |
| 5 | QA & hardening (local) | `qa` | traceability matrix passing, audits clean |
| 6 | Release candidate | `release` | versioned build verified locally, runbook approved |
| 7 | Deploy | `deploy` | staging verified, production live / store approved |
| 8 | Iterate | `iterate` | per change request |

**Local first.** Phases 0–5 develop and test on your machine only (local services, seed
data, fakes for paid services). Phase 6 freezes a versioned release candidate and verifies
it locally. Only phase 7 ships it — staging first, then production — with every external
step approved by you. A hook blocks deploy/publish commands before phase 7.

**Machine-safe builds.** Builds, test suites, simulators and dev servers run inside a
resource budget that setup detects from your RAM and CPU (`bma_state.py resources`). A
machine with 16 GB or less gets one heavy run at a time and 2 test workers. Heavy commands
go through `scripts/bma_heavy.py`. It queues runs across parallel agents and worktrees,
caps test workers (`BMA_TEST_WORKERS`), and stops a run on critical memory pressure before
the machine runs out of memory. A hook blocks build and test commands that skip the
wrapper, and blocks watch mode (`bma_state.py set enforce_heavy false` turns the check off).
Override the budget with
`bma_state.py resources --slots N --builders N --workers N`.

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
| `/build-my-app:ui [stop\|status]` | Open the live web view of the agents, the conversation, and progress |

## Web UI

```
/build-my-app:ui
```

Opens a local page (127.0.0.1 only, with a random access token in the link) that shows the
run as a small 3D service center:

- **Front desk** (along the bottom): the conversation, from both sides. Type in the page or in
  the terminal; both show up here, with Claude's replies and short notes when it hands out work
  or an agent finishes. Cards for things that need you sit beside it.
- **Back office:** each subagent appears as a clay figure when it starts. It walks in, works at
  a desk and says what it is doing, waits on the bench while a heavy build or test run is
  queued, shows a red mark after three failed heavy runs in a row, and leaves when it is done.
  Each agent type has its own color and prop. The Agents list in the left sidebar shows the
  same information.
- **Progress** (left sidebar, under Agents): phases and gates, open decisions, review loops, the machine budget and memory
  pressure, and the environment recorded in setup.

**Chatting from the page** uses Claude Code
[channels](https://code.claude.com/docs/en/channels), a research preview. Start Claude Code in
the project with the plugin's channel turned on:

```bash
claude --dangerously-load-development-channels plugin:build-my-app@taro-tools
```

Claude Code shows a warning screen for development channels at each start; choose "I am using
this for local development". Until channels leave the preview, a plugin outside Anthropic's
allowlist needs this flag. Without it, the page still works as a live view, and the chat box
says how to turn chat on. Messages typed in the page reach the session like terminal messages
(`← bma: …` in the terminal), and Claude's final answer of each turn appears in the page.
Each message shows whether it was delivered and whether Claude reacted. Organizations on
claude.ai Team or Enterprise must enable channels first (`channelsEnabled`).

**Things that need you** appear as cards above the chat box:

- **Tool approvals.** When Claude Code asks before running a tool, the same prompt appears in
  the page with *Allow once* and *Deny*. The terminal prompt stays open; the first answer
  counts, and a card closes by itself when you answer in the terminal.
- **Hard stops stay in the terminal.** Deploying, publishing, submitting, force-pushing, and
  tools that look like payments, messages, or secrets can be *denied* from the page but only
  *allowed* in the terminal. The chat bridge enforces this itself, not just the page.
- **Gates and decisions.** A phase waiting at its gate, and each open decision with its
  options (the recommended one marked), get buttons that put your answer in the chat box to
  check and send.
- **Claude's questions.** When Claude asks a multiple-choice question while you have the page
  open (and looked at it in the last minute), the question comes to the page instead of the
  terminal: pick options, or type your own answer. *Answer in the terminal* moves it back, and
  so does closing the page or waiting 5 minutes. This works without the channel flag. A hook
  runs before the terminal dialog, so the question is in one place at a time, never both.

The UI adds no load when it is off. Its hooks run in the background and do nothing unless the
server is running. The chat bridge (`bma_channel.py`, an MCP server the plugin declares) starts
with every session but stays idle outside build-my-app projects and in sessions started without
the channel flag, so those sessions never take messages meant for another. The 3D view loads
three.js from jsDelivr (pinned, with an integrity hash); offline, the page falls back to the
list. `/build-my-app:ui stop` closes it.

The **Colors** menu in the header switches palettes (Mint, Sky, Slate, or the warm Clay) for the
page and the room; each browser remembers its choice, and `?palette=sky` in the link forces one.

To see it without a real run, play the demo. It builds a throwaway project in phase 4 and replays a
short story through the same hooks: two features built in parallel, the build queue, a code
review, an accessibility audit, and a feature that gets stuck and rescued. It also stands in for
the Claude Code session, so you can try the interactive parts: chat (canned replies), a tool
approval and a hard stop, and a question from Claude.

```bash
python3 scripts/bma_ui_demo.py --open        # loops until Ctrl-C; --once, --speed 2
```

## Components

- **Skills**: `core`, one per phase (`setup` … `release`, `deploy`, `iterate`), `spike-resolver`,
  spec tools (`spec-context`, `spec-author`, `spec-derive`), stack packs
  (`stack-ios`, `stack-web`, `stack-android`, `stack-backend`).
- **Agents**: product-strategist, market-researcher, spec-reviewer, design-auditor,
  ui-critic, architect, license-auditor, spike-runner, feature-builder, code-reviewer,
  security-auditor, a11y-auditor, perf-analyst, qa-runner, stuck-resolver, release-manager.
- **Hooks** (no-ops outside build-my-app projects): session orientation, spec-ID context
  injection, state/generated-file edit guard, destructive-command, deploy-before-phase-7, and
  unregistered-dependency guard, spec lint after spec edits, compaction log, pause notice on stop.
- **Web UI**: `scripts/bma_ui.py` (local server), `scripts/bma_channel.py` with `.mcp.json`
  (chat bridge, an MCP channel), `hooks/ui_events.py` (event recorder), `scripts/bma_events.py`
  (event log), `ui/` (the page and the 3D room), `scripts/bma_ui_demo.py` (demo).
- **Scripts**: `scripts/bma_state.py` (workflow state machine, stored in
  `.build-my-app/state.json` in the project).
- **Project template** (`templates/project/`): spec tree with templates and rules, spec lint
  and query tools (vendored into the project so CI can run them), `CLAUDE.md`.

## Status

v0.6.0 — skeleton. Web UI (`/build-my-app:ui`) with a live agent room, chat, approvals, and Claude's questions in the page. Builds and tests stay within a
machine resource budget. Phases 0–1 and the core protocols are fully specified; phases 2–8 have
complete step lists but are untested end to end. See `ROADMAP.md`.

## License

Source-available, **not open source**. You may read the code and use the plugin for
personal, non-commercial purposes. Copying, redistributing, publishing modified versions,
and any commercial use are not allowed without written permission. See [LICENSE](LICENSE).
