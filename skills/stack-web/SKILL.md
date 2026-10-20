---
name: stack-web
description: Stack pack for web apps in build-my-app — project layout, build/test commands, browser runs and screenshots, code generation, accessibility/performance tooling, and hosting release and deploy steps. Use in phases 3–7 when the chosen platform is the web.
---

# Stack pack — Web

- **Layout**: framework chosen in phase 3 (ADR); modules as packages/folders per spec.
- **Build/test**: package scripts for build, unit tests, end-to-end tests (one per FLOW).
- **Run & screenshot**: dev server + browser automation (browser tools/MCP when available) for
  state screenshots and visual regression.
- **Codegen**: schema → types; tokens → CSS variables/theme; `copy.md` → message catalog.
- **Quality**: automated accessibility checks + manual screen-reader pass; performance budgets
  (load, interaction) per NFRs.
- **Local env**: dev server + local API/services (containers or mocks), `.env.local`;
  `npm run dev` (or equivalent) is the one run command.
- **Release (phase 6)**: production build (`npm run build`), served locally with the
  production server/preview (`npm run preview`/`start`) and tested with the e2e suite.
- **Deploy (phase 7)**: user-owned — hosting account, domain/DNS, environment secrets,
  analytics consent. Deploy the built artifact to a staging/preview URL, run e2e against it,
  then promote the same build to production; keep the previous deployment for rollback.
