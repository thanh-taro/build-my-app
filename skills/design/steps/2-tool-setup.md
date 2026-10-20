# Step 2 — Design tool selection & setup

1. **Detect** which design tools are reachable in this session (connected MCP servers or
   artifact types: e.g. Claude Design artifacts, Figma, Penpot) and the user's experience.
2. **Present options** with a recommendation (decision kind: design):
   | Option | Best when |
   |---|---|
   | Claude Design / artifact pages | Fast iteration, solo builder, shareable links |
   | Figma (MCP) | A designer is involved, or the user already works in Figma |
   | Penpot | Open-source preference |
   | Code-first (platform previews / web prototype) | Developer-led, small app, design ≈ implementation |
3. **Set up**: guide connector install and authentication (a human step — never handle the
   user's credentials). Verify access with a harmless read call.
4. **Write `adapters/design.md`**: frame naming `<SCR-ID> / <state>`, component naming
   `<CMP-ID> / <variant>`, how tokens are imported, how COPY IDs are attached.
5. Record: `bma_state.py set design_tool '"<tool>"'`.
