---
name: stack-backend
description: Stack pack for backend services in build-my-app — API-first layout, contract and integration tests, local environments, security baseline, and release and deployment steps. Use in phases 3–7 when the app needs a server, API, or database.
---

# Stack pack — Backend

- **Layout**: API contract first (from domain + features), then services per module.
- **Build/test**: unit, contract (API schema), and integration tests with local containers.
- **Security baseline**: authn/authz model ADR, secrets via environment (never in code),
  input validation, rate limiting, logging without personal data.
- **Data**: migrations versioned; schema derived from `specs/10-domain/`.
- **Local env**: `docker compose` (or equivalent) runs the service with its database,
  queues, and caches; migrations + seed data on `make setup`; third-party APIs faked locally.
- **Release (phase 6)**: build the versioned image/artifact locally, run contract and
  integration tests against it, dry-run migrations on a copy of local data; write
  infrastructure definitions (not applied) and the runbook.
- **Deploy (phase 7)**: user-owned — cloud account, billing, domains, production secrets.
  Push the artifact, apply infrastructure and migrations to staging, verify, then promote the
  same artifact to production; rollback = previous artifact + backward-compatible migrations.
