---
name: stack-backend
description: Stack pack for backend services in build-my-app — API-first layout, contract and integration tests, local environments, security baseline, and deployment steps. Use in phases 3–6 when the app needs a server, API, or database.
---

# Stack pack — Backend

- **Layout**: API contract first (from domain + features), then services per module.
- **Build/test**: unit, contract (API schema), and integration tests with local containers.
- **Security baseline**: authn/authz model ADR, secrets via environment (never in code),
  input validation, rate limiting, logging without personal data.
- **Data**: migrations versioned; schema derived from `specs/10-domain/`.
- **Release**: user-owned — cloud account, billing, domains, production secrets; Claude
  prepares infrastructure definitions and runbooks.
