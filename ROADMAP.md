# Roadmap

- [ ] Dogfood phases 0–1 on a new idea; tune question rounds and the review-loop prompts.
- [ ] Reverse-spec path for existing codebases (phase 1, brownfield).
- [ ] Phase 2: style-tile page template; screenshot capture per design tool; design adapter templates.
- [ ] Phase 3/4: codegen scripts (schema → types, tokens → theme, copy → string catalog) per stack.
- [ ] Traceability script (AC ↔ test ↔ result) shared by phases 4–5.
- [ ] Workflow scripts for fan-out reviews (spec review, design audits, parallel feature waves).
- [ ] Cost estimate per phase shown before large fan-outs.
- [x] Self-test script for `bma_state.py`, hooks, and the project template (`scripts/selftest.sh`).
- [ ] Turn the self-test into assertions and run it in CI.
- [x] Web UI v0.3: watch-only room, feed, and progress panel (`/build-my-app:ui`).
- [x] Web UI v0.4: chat from the page through a Claude Code channel (stdlib MCP server, `reply` tool,
      transcript mirror as a fallback when Claude answers only in the terminal).
- [x] Web UI v0.5: answer decisions and approve gates and tool prompts from the page (permission relay);
      hard stops stay terminal-confirmed.
- [x] Web UI v0.6: answer Claude's multiple-choice questions (AskUserQuestion) in the page.
- [x] Web UI v0.7: open the app from the page (previews: web/API URL, iOS Simulator, Android emulator).
- [ ] Previews on a phone (QR code; needs the dev server on the local network).
