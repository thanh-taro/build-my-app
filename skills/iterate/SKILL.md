---
name: iterate
description: Phase 8 of build-my-app and the change-request procedure — turn feedback, bugs, and new ideas into spec changes, analyze impact, review, and rebuild only what is affected; start the next milestone. Use for /build-my-app:change and after deploy.
---

# Phase 8 — Iterate & change requests

Follow **core**.

## Change-request procedure
1. **Classify**: bug (spec is right, code is wrong) · change (behavior changes) · new feature.
2. **Spec first** (spec-author skill) — except pure bugs, which get a failing test first.
3. **Impact**: `python3 tools/spec_query.py refs <ID>` for every changed ID → list affected
   specs, designs (by SCR/CMP), modules, tests.
4. **Review**: review-loop protocol on the changed and affected specs.
5. **Approve** per autonomy (product decisions always go to the user in guided/balanced).
6. **Rebuild only the affected parts, locally**: design loop for affected frames; feature
   pipeline for affected features; regression suite on the local environment.
7. **Ship**: when the user wants the change live, cut a new candidate (release skill) and
   deploy it (deploy skill). Urgent fixes take the same path, with a smaller scope.
8. **Record**: changelog entry; statuses; release notes when shipped.

## Next milestone
Promote the next milestone's candidates in `specs/60-delivery/roadmap.md` into features
(phase 1.2 → 1.3), then run design, build, QA (local), release, and deploy again for that
scope.

## Feedback intake
Collect user feedback, crash reports, analytics, and store reviews into
`.build-my-app/reports/feedback.md`; propose the top items as change requests.
