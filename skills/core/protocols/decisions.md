# Decision protocol

## Classify every decision
| Kind | Examples | Who decides |
|---|---|---|
| product | scope, priorities, behavior users notice, trade-offs | user (guided/balanced); Claude may decide reversible ones in autopilot and log them |
| design | style direction, design approval | user (guided/balanced) |
| money | paid services, subscriptions, assets, developer accounts | **always user** |
| legal | licenses, terms, privacy, data leaving the device | **always user** |
| release | publishing, submitting, inviting testers | **always user** |
| technical | libraries within policy, structure, naming, test details | Claude decides and records an ADR or changelog line |

## How to ask
1. Record it: `bma_state.py decide add "<question>" --options "A|B|C" --recommend A --kind <kind>`.
2. Ask with the AskUserQuestion tool when available: recommended option first, labelled
   "(Recommended)", each option with its consequence. Batch related questions (max 4).
3. Record the answer: `bma_state.py decide answer D-xxx "<answer>"`.
4. Write the outcome where it belongs (spec, ADR, changelog). The decision log is not the
   source of truth — the specs are.

## How to decide alone
- Only for `technical` decisions (and reversible product details in autopilot).
- Prefer the reviewers' suggested default; record it (ADR for architecture-level, changelog
  line otherwise) and mention it in the phase summary under "Choices I made".
