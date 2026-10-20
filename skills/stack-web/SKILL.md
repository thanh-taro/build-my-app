---
name: stack-web
description: Stack pack for web apps in build-my-app — project layout, build/test commands, browser runs and screenshots, code generation, accessibility/performance tooling, and hosting release steps. Use in phases 3–6 when the chosen platform is the web.
---

# Stack pack — Web

- **Layout**: framework chosen in phase 3 (ADR); modules as packages/folders per spec.
- **Build/test**: package scripts for build, unit tests, end-to-end tests (one per FLOW).
- **Run & screenshot**: dev server + browser automation (browser tools/MCP when available) for
  state screenshots and visual regression.
- **Codegen**: schema → types; tokens → CSS variables/theme; `copy.md` → message catalog.
- **Quality**: automated accessibility checks + manual screen-reader pass; performance budgets
  (load, interaction) per NFRs.
- **Release**: user-owned — hosting account, domain, environment secrets, analytics consent.
