# Banking-RM

A lightweight prototype for institutional / financial-institutions relationship managers.

The MVP is deliberately **outside the bank core system**:
- public-data intelligence
- manual optional internal inputs
- credit snapshot
- opportunity detection
- meeting discovery playbook

## First verified demo client
Korea Development Bank (KDB)

## MVP modules
1. **Credit Intelligence** — ratings, government support, capital, asset quality, funding.
2. **Opportunity Intelligence** — funding, DCM, FX/CCS, syndication, PF, deposits/MM, trade.
3. **Meeting Intelligence** — what changed, why it matters, what to ask next.
4. **Discovery Playbook** — indirect questions to uncover funding plans, wallet gaps, buying criteria and pipeline.
5. **Early Warning** — credit deterioration and business triggers.

## Web entrypoint

Run:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

The Streamlit entrypoint provides three views:
- **KDB Demo** — view the generated KDB intelligence brief and download the Markdown report / verified JSON snapshot.
- **New Institution** — upload annual reports, investor presentations, rating reports and other approved source documents to create a reusable source pack for another institution.
- **Customize Report** — upload an existing Markdown/text report plus policy/rule files, apply supported rules, preview/edit and download the customized report.

Supported rule directives in the current deterministic prototype:

```text
HIDE: Evidence ledger
RENAME: Opportunity Intelligence => Business Opportunities
MAX_QUESTIONS: 5
DISCLAIMER: Internal working draft — verify before client use
REQUIRE: source | reporting period | reliability
```

Natural-language policy files can be uploaded and inspected, but only the supported directives above are automatically enforced in this version. A future LLM-backed policy interpreter can sit behind the same UI without changing the source/quality model.

## Reuse for other institutions

The architecture is reusable, but **9/10+ reliability is not automatically portable**. Each institution/source family needs validated mappings for its own annual report, investor presentation, ratings and funding documents.

Use `config/institution_template.json` as the starting point. The generic workflow is:

`institution config -> approved sources / uploads -> text extraction -> institution-specific validation -> structured snapshot -> quality gate -> RM intelligence -> meeting discovery -> downloadable report`

For a new bank, policy bank, NBFI, sovereign fund or asset manager, the UI/source-pack layer works immediately. Credit-grade metric extraction should stay in `unverified` status until the relevant source-specific parsers and consistency checks are added.

## Automated public-data pipeline

The `kdb-auto-pipeline` branch contains the first end-to-end verified workflow:

`KDB public pages / PDFs -> PDF & HTML extraction -> structured metrics -> evidence snippets -> quality/freshness controls -> RM intelligence brief`

### Run locally

```bash
python -m pip install -r requirements.txt
python -m src.kdb_pipeline
python -m src.coverage_enrichment
python -m src.provenance_fixups
python -m src.rm_intelligence_enrichment
python -m src.rm_brief
```

Outputs:
- `data/kdb_public_snapshot.json` — structured extraction with source metadata and evidence snippets.
- `reports/kdb_auto_brief.md` — auto-generated credit, opportunity and meeting brief.
- `web/` — verified export for a web/mobile front end.

The pipeline intentionally leaves uncertain or missing metrics as `n/a`; it does not invent figures.

### Source configuration

KDB source URLs live in `config/kdb_sources.json`. The collector can:
- read known investor-presentation PDFs;
- inspect KDB Annual Report and Funding Programme pages;
- discover matching PDF links;
- extract PDF text;
- detect validated credit/funding metrics;
- retain source URLs and evidence snippets for verification.

### CI

`.github/workflows/kdb-pipeline.yml` runs tests and the full public-data pipeline on pushes and pull requests, then uploads the generated snapshot, RM brief and web export as workflow artifacts.

## Data principle
No bank-system API is required for the MVP. Public sources are primary. Internal exposure, limits, revenue and meeting notes are optional manual inputs and should only be used in an approved environment.

## Guardrails
- Separate extracted facts from RM inference.
- Do not infer missing financial values.
- Verify material figures against the source document before credit or client use.
- Uploaded source packs are `unverified` until source-specific validation rules are configured.
- Never auto-send client communication or alter internal bank limits/exposures.
