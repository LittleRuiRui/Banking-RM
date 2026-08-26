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

## v0.2 automated public-data pipeline

The `kdb-auto-pipeline` branch adds a first end-to-end workflow:

`KDB public pages / PDFs -> PDF & HTML extraction -> structured metrics -> evidence snippets -> RM intelligence brief`

### Run locally

```bash
python -m pip install -r requirements.txt
python -m src.kdb_pipeline
python -m src.rm_brief
```

Outputs:
- `data/kdb_public_snapshot.json` — structured extraction with source metadata and evidence snippets.
- `reports/kdb_auto_brief.md` — auto-generated credit, opportunity and meeting brief.

The pipeline intentionally leaves uncertain or missing metrics as `n/a`; it does not invent figures.

### Source configuration

KDB source URLs live in `config/kdb_sources.json`. The collector can:
- read known investor-presentation PDFs;
- inspect KDB Annual Report and Funding Programme pages;
- discover matching PDF links;
- extract PDF text;
- detect a first set of credit/funding metrics;
- retain source URLs and evidence snippets for verification.

### CI

`.github/workflows/kdb-pipeline.yml` runs tests and the full public-data pipeline on pushes and pull requests, then uploads the generated snapshot and RM brief as workflow artifacts.

## Data principle
No bank-system API is required for the MVP. Public sources are primary. Internal exposure, limits, revenue and meeting notes are optional manual inputs and should only be used in an approved environment.

## Guardrails
- Separate extracted facts from RM inference.
- Do not infer missing financial values.
- Verify material figures against the source document before credit or client use.
- Never auto-send client communication or alter internal bank limits/exposures.
