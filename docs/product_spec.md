# Product Spec — v0.1

## User
Institutional / FI Relationship Manager.

## User problem
RMs spend too much time assembling fragmented public information and too little time deciding:
- what changed
- whether it matters for credit
- where the next wallet opportunity is
- what to ask in the next meeting

## Output
A one-page brief plus a meeting discovery playbook.

## Workflow
Public sources -> structured extraction -> credit implications -> opportunity mapping -> discovery questions -> RM action.

## Public-data sources
- Annual reports / audited financial statements
- Investor presentations
- Funding programmes / bond prospectuses
- Ratings
- Central-bank / government policy releases
- Relevant news
- Market data, where licensed

## Optional manual internal inputs
- Current group limit / sub-limit
- Current exposure
- Existing products
- Revenue / wallet
- Last meeting notes
- Current pipeline

## Guardrails
- Never infer missing financial figures.
- Separate facts from inference.
- Attach source and date to every material fact.
- Do not auto-send client communications.
- Do not auto-change limits, exposures or booking-system data.
- Flag sensitive/internal inputs as manual and environment-restricted.
