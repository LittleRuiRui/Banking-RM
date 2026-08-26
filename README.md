# Banking-RM

A lightweight prototype for institutional / financial-institutions relationship managers.

The MVP is deliberately **outside the bank core system**:
- public-data intelligence
- manual optional internal inputs
- credit snapshot
- opportunity detection
- meeting discovery playbook

## First demo client
Korea Development Bank (KDB)

## MVP modules
1. **Credit Intelligence** — ratings, government support, capital, asset quality, funding.
2. **Opportunity Intelligence** — funding, DCM, FX/CCS, syndication, PF, deposits/MM, trade.
3. **Meeting Intelligence** — what changed, why it matters, what to ask next.
4. **Discovery Playbook** — indirect questions to uncover funding plans, wallet gaps, buying criteria and pipeline.
5. **Early Warning** — credit deterioration and business triggers.

## Quick start
```bash
python -m src.report_generator
```

This renders `reports/kdb_rm_intelligence_generated.md` from `data/kdb_sample.json`.

## Data principle
No bank-system API is required for v0.1. Public sources are primary. Internal exposure, limits, revenue and meeting notes are optional manual inputs and should only be used in an approved environment.
