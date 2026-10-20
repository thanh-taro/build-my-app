# Step 4 — Design loop (per design phase)

Review-loop protocol, loop name `design-<phase>`.

1. **Make**: for each frame, load the spec bundle; build it in the chosen tool using tokens
   and COPY text only; name it per the adapter. Prefer reusing components over ad-hoc shapes.
2. **Spec audit** — `design-auditor` agent: every state/variant present; every requirement
   that affects UI is visible; correct copy IDs; tokens only; flows connect.
3. **UI/UX critique** — `ui-critic` agent, from screenshots: hierarchy, spacing rhythm and
   grid, alignment, density, contrast, touch targets, platform conventions, consistency
   across screens, empty/error clarity.
4. **Fix** findings; behavior questions go back to the specs first (spec-author skill).
5. **User review** at the end of each design phase (guided/balanced): show the frames, the
   audit results, and choices made. Apply feedback, then continue with the next phase.
