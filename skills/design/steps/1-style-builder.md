# Step 1 — Style builder (collaborative)

1. **Discover** (one question round + references):
   - 3–5 brand adjectives (e.g. calm, playful, pro);
   - apps/sites the user likes or dislikes visually, and why (screenshots welcome);
   - context of use (one hand, outdoors, dark rooms, older users…);
   - light, dark, or both; platform conventions to follow strictly or loosely.
2. **Propose 2–3 style directions** as one visual page (an artifact when available, otherwise
   an HTML file under `.build-my-app/reports/`): palette with roles, type scale, spacing
   scale and grid, corner radius, elevation, iconography, motion, a sample screen per
   direction built from a real M-1 screen spec.
3. **User picks or mixes** (decision kind: design). Iterate at most 2 rounds.
4. **Write the result into the specs**:
   - `specs/30-experience/tokens.json` (W3C DTCG format) — colors by role, spacing, radius,
     typography, motion, sizes (incl. touch target);
   - a short "Style" section in `specs/30-experience/` (principles of the look & feel);
   - run a contrast check for every text/background pair that carries text; fix tokens that
     fail WCAG AA (4.5:1 body text, 3:1 large text and UI elements).
5. `python3 tools/spec_lint.py` → 0 errors.
