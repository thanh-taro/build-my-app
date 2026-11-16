# Resource budget protocol

Builds, test suites, simulators/emulators, dev servers, and profilers are heavy. Parallel
agents that each run them at full width can exhaust memory and crash the user's computer.
This protocol always applies, at every autonomy level.

## The budget
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_state.py resources` shows it. It is detected in
setup from RAM and CPU. The user can change it, e.g. `resources --slots 1 --builders 1 --workers 1`.
- `heavy_slots`: how many heavy commands may run at once on this machine.
- `parallel_builders`: how many `feature-builder` agents may run in one wave.
- `test_workers`: how many worker processes or threads one test run may use.

Machines with 16 GB or less get one slot. Work there is sequential.

## Rules
1. **Every heavy command goes through the wrapper.** This covers builds, test runs, e2e,
   app launches with UI tests, and profiling:
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_heavy.py --label <F-ID|task> -- <command>`.
   The wrapper limits how many run at once across all agents and worktrees. It exports
   `BMA_TEST_WORKERS`, runs the command at low priority, and stops it on critical memory
   pressure (exit 137). On exit 137, do not retry the same command. Lower the scope or the
   budget first. The bash guard hook blocks unwrapped build and test commands, and any
   watch mode. Only the user turns that check off (`bma_state.py set enforce_heavy false`).
2. **Cap test workers in the project's config**, not per command. Every runner reads
   `BMA_TEST_WORKERS` and falls back to 2 (see the stack pack). Never use "all cores",
   `-n auto` without the cap, or unlimited forks.
3. **Run tests narrowly while iterating.** Run the tests of the feature or module being
   changed. The full suite runs once per feature at verification, and again after each
   merge. It never runs from several agents at the same time.
4. **One simulator/emulator/browser stack at a time.** Reuse the booted device. Do not
   create a new one per agent or per worktree. Shut down what you started when you finish.
5. **One local backend stack.** Worktrees share the running `docker compose` services
   instead of starting their own copy, unless the feature changes them.
6. **Clean up after each feature.** Stop dev servers and watchers you started. Let build
   daemons expire (idle timeout in the project config), or stop them once no other run is
   active. Remove merged worktrees, because each one holds its own build caches and daemons.
7. **Never use watch mode** (`--watch`, `vitest` without `run`, `jest --watch`) in agents.
   It never exits and holds memory.
8. **Respect warnings.** If `resources` shows pressure `warn`/`critical` before a wave,
   shrink the wave or run sequentially, and tell the user in one line.
