# Preview: let the user try the app

Whenever the app is running on this machine in a state worth trying, record it so the web UI
(`/build-my-app:ui`) shows an **Open app** button. Do this:

- after a feature passes local verification (build step 4), with the latest dev build;
- in QA, before asking for the G5 approval;
- for a release candidate, after it is verified locally (release step 3), before G6.

```bash
# web or API: the local URL (localhost only); give the dev server's pid if you started it
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_preview.py add --kind web --target http://localhost:5173 \
  --label "Dev build after F-004" --cmd "npm run dev" --pid <pid> --screenshot <a PNG you captured>
# iOS Simulator / Android emulator: the installed app's bundle id or package name
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bma_preview.py add --kind ios --target com.example.habits \
  --label "Release candidate 1.2.0" --screenshot <a PNG you captured>
```

- Use a label the user understands: what build it is and what changed ("Dev build after F-004",
  "Release candidate 1.2.0-rc.1"). A new preview of the same kind and target replaces the old one.
- Pass `--screenshot` with one of the screenshots you already took while verifying.
- Previews are local only. Never record a staging or production URL here (that is phase 7).
- **Resource exception:** one preview may stay running after the feature (one dev server, or the
  one booted simulator/emulator), so the user can try it. It counts toward the budget. Stop it
  when the user is done, when a heavier run needs the memory, or when the UI is closed (the UI
  server stops a preview whose `--pid` you gave after 30 minutes with no page open).
- When the user asks to restart a stopped preview, start it the same way (`--cmd`) through the
  resource protocol, then record it again.
