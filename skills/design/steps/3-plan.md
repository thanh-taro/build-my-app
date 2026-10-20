# Step 3 — Design plan

1. **Inventory** from specs: `spec_query.py list SCR`, `list CMP`, `list FLOW`; for each
   screen, its states table; for each component, its variants.
2. **Size it**: count screens × states + components × variants.
3. **Split into design phases** when large (> ~15 frames):
   - D1: components (from tokens) — everything else is built from them;
   - D2: the primary flow (e.g. FLOW-01) happy path;
   - D3: remaining screens' default states;
   - D4: empty / loading / error / limit states and dialogs.
4. Write `.build-my-app/reports/design-plan.md` (phases, frames, order) and confirm with the
   user in guided mode.
