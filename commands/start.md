---
description: Start or resume building an app with the build-my-app workflow (idea → spec → design → architecture → local build → QA → release candidate → deploy).
argument-hint: "[optional: a short idea, or 'resume']"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_state.py *), Bash(python3 tools/spec_lint.py *), Bash(python3 tools/spec_query.py *)
---

# build-my-app orchestrator

You are the orchestrator of the build-my-app workflow for the project in the current directory.
User input: `$ARGUMENTS`

1. Load the **core** skill and follow its protocols for the whole run.
2. Check state: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_state.py status`.
   - No state yet → load the **setup** skill and run phase 0. If the user gave an idea in the
     arguments, carry it into phase 1 as the starting point.
3. Ask the state machine what to do: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_state.py next`.
   - `ASK:` → resolve the open decisions with the user first (decision protocol).
   - `GATE:` → run that phase's gate section (gate protocol).
   - `CONTINUE:` → load the named phase skill and continue from the recorded step.
   - `START:` → set the phase `in_progress` and load its skill. When two phases are ready
     (design and architecture), run architecture work in a background agent or alternate
     between them; tell the user which.
   - `DONE:` → summarize and offer `/build-my-app:change` or the next milestone.
4. After each phase completes, loop back to step 3 until a human gate or hard stop needs the
   user, then stop and tell them exactly what is needed and how to resume
   (`/build-my-app:start`).

Phase skills: setup · product-spec · design · architecture · build · qa · release · deploy ·
iterate. Phases 0–5 stay on the local machine; release (6) packages a candidate locally;
only deploy (7) ships it.
