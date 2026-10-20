---
name: product-spec
description: Phase 1 of build-my-app — brainstorm a realistic, valuable idea with the user, research the market, choose platforms and MVP scope, write the spec-as-source, and run the spec review loop until the user marks specs ready. Use when the workflow is in the product-spec phase.
---

# Phase 1 — Product & spec

Follow **core**. Load the **spec-author** skill before writing specs.
Reference: the spec rules in `specs/README.md`; templates in `specs/_templates/`.

## 1.1 Idea brainstorming (collaborative, iterative)
Work in short rounds; summarize after each; never dump a wall of questions.
1. **Problem**: who has it, how often, how they cope today, why now.
2. **Market** — use the `market-researcher` agent: competitors, pricing, what users praise and
   complain about (store reviews, forums), gaps. Cite sources.
3. **Positioning**: one-line pitch, the 2–3 differentiators, explicit non-goals.
4. **Platforms**: recommend with reasons (audience, device capabilities, distribution, cost);
   the user decides (decision kind: product).
5. **Business & legal**: monetization; content/asset licensing; privacy and data handling;
   store policies that constrain the idea. Flag hard stops (money/legal) as decisions.
6. **Feasibility & risks** — use the `product-strategist` agent to challenge the idea; list
   technical unknowns → record as spike candidates (`bma_state.py set spike_candidates '<json>'`).
7. **MVP scope**: milestones M-1…M-n; keep M-1 to what proves the core value.
Output: `.build-my-app/reports/vision-brief.md`. Ask the user to approve it (decision kind:
product) before writing specs.

## 1.2 Idea → spec
1. Fill `specs/00-product/` (vision, personas, principles, glossary) from the brief.
2. `specs/10-domain/` (model, rules, data schema) — entities, invariants, limits.
3. `specs/20-features/` — one file per M-1 feature from the template, with R#/AC#, plus
   `_index.md`. Keep each feature readable in ~2 minutes.
4. Thin first versions of `30-experience/` (screens/flows/copy), `50-quality/` (NFRs,
   analytics), `60-delivery/` (roadmap, changelog). Phases 2 and 3 complete them.
5. `python3 tools/spec_lint.py` → 0 errors. Fill `CLAUDE.md` placeholders.

## 1.3 Spec review loop
Review-loop protocol with `spec-reviewer` agents: split by feature group (≈5 features each)
plus one cross-cutting reviewer (domain/schema, glossary, copy, NFR, analytics, roadmap).
Product decisions surfaced by reviewers go to the user in one batched round, with
recommendations.

## Gate G1
Automated: lint 0 errors / 0 warnings; every feature has R + AC; no open decisions of kind
product; last review round had no blockers.
Approval: the user reviews the spec summary and sets features to `ready` (they may ask you to
do it on their behalf — record that in the changelog). Then `bma_state.py gate product-spec pass`.
