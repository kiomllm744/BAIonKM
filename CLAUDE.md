# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Flask web app for traditional Chinese medicine (TCM) research. A user enters a **disease** and one or more **prescriptions** (lists of herbs); the app finds which disease-associated genes each prescription's herbs target, computes the genes unique to each prescription, runs pathway enrichment on them, and optionally generates an LLM-written comparative analysis. Used to hypothesize mechanisms of action for herbal formulas against a disease.

## Commands

```powershell
# Setup (Windows; .venv is already present)
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python download_db.py          # fetches diseaseportal.db from Google Drive (gitignored, too large for git)

# Run locally — http://localhost:5000, debug on unless FLASK_ENV=production
python app.py

# Production (Render / Procfile)
gunicorn app:app --bind 0.0.0.0:$PORT
```

There is **no test suite, linter, or build step** in this repo. Verify changes by running the app.

Required environment (local: `.env`; prod: Render dashboard, `sync: false` keys in `render.yaml`):
- `GEMINI_API_KEY` — without it, analysis still works but the AI-analysis endpoint returns 503.
- `UMLS_API_KEY` — optional; without it the UMLS terminology step is silently skipped (Open Targets still works).
- `SECRET_KEY`, `DATABASE_URL` (Postgres in prod; `postgres://` is auto-rewritten to `postgresql://` in `config.py`), `DEMO_USERNAME`/`DEMO_PASSWORD`.

## Architecture

### Two data sources, deliberately split
- **Local DB (`herbs` table, ~437 herbs from BATMAN-TCM)** is the *only* data stored locally — herb → compound → target-gene rows. This is the large SQLite/Postgres file downloaded via `download_db.py`.
- **Disease data is always live online from Open Targets** (GraphQL, `opentargets_service.py`). Disease EFO/MONDO IDs, associated genes, and association scores are never stored locally beyond caching. `Config.SQLALCHEMY_DATABASE_URI` defaults to local `diseaseportal.db`.

### The analysis pipeline (`services.py::analyze_prescriptions`)
1. **Resolve disease → Open Targets ID.** `resolve_disease_to_open_targets` asks UMLS (`umls_service.py`) for standardized name candidates, then tries each against Open Targets search. **UMLS is only a terminology bridge — Open Targets is the source of truth for IDs, genes, and scores.** A raw `EFO_*`/`MONDO_*`/`Orphanet_*` input bypasses resolution.
2. **Fetch disease genes + scores** from Open Targets for that EFO ID.
3. **Per prescription, batch-query the local `herbs` table** for the union of target genes (one `IN (...)` query per prescription, not per herb). Herbs not found are reported as `missing_herbs`.
4. **Set math:** common genes = disease ∩ herb genes; unique genes = genes in one prescription but no other.
5. **Enrichment:** the *unique* gene lists are uploaded to Enrichr and scored against the `DisGeNET` library (`Config.DEFAULT_GENE_LIBRARY`), filtered to adjusted p < 0.05. Enrichr upload + fetch run in parallel via `ThreadPoolExecutor`.
6. Result dict is saved to the `analysis_results` table and rendered into `result.html`.

### AI analysis is a separate, client-triggered second pass
`result.html` JS reconstructs `prescription_enrichments` from the rendered enrichment tables and POSTs to `/api/ai-analysis`. That calls `llm_service.py::generate_full_ai_analysis`, which prompts **Gemini** (model `gemini-3.5-flash` in `get_gemini_response`) for a strict-JSON `summary_table` + `detailed_analysis` + `clinical_questions`. The result is saved back onto the row's `ai_analysis_json` column. LLM responses are defensively parsed (`extract_json_from_response` strips markdown fences and control chars) because the model often wraps or dirties the JSON.

### Caching
`external_lookup_cache` table caches both Open Targets (15 days, plaintext cache key) and UMLS (`UMLS_CACHE_TTL_DAYS`, sha256 cache key) responses. Same table, different `provider` prefixes and key schemes — don't assume one keying scheme.

### Request flow / routes (`routes.py`)
All routes live in one `main_bp` blueprint. Autocomplete endpoints (`/api/diseases`, `/api/herbs`) feed the frontend; `/api/diseases` additionally filters Open Targets suggestions through `_is_relevant_open_targets_suggestion` (token-overlap heuristic with stopword/location lists) to drop unrelated guesses. Herb autocomplete is **bilingual** — Korean (Hangul) or English/Pinyin input, mapped via `herb_mappings.py` (`HERB_NAME_MAPPINGS`, ~437 entries).

## Conventions and gotchas specific to this repo

- **Engines are created per-module, not shared.** `app.py` initializes flask-sqlalchemy's `db`, but `routes.py`, `services.py`, `opentargets_service.py`, and `umls_service.py` *each* call `create_engine(...)` + `sessionmaker(...)` and use raw sessions. The flask-sqlalchemy `db` is essentially only used for model definitions. When adding queries, follow the local `Session()` pattern with a `try/finally: session.close()`.
- **Schema migration is hand-rolled at import time.** `routes.py::init_results_table()` runs on import: it creates/`ALTER TABLE`s `analysis_results` (adding `ai_analysis_json` if missing) and creates `external_lookup_cache` (`checkfirst=True`). There are no migration tools (no Alembic). The `herbs` table is **not** created here — it ships inside the downloaded DB. New columns need similar manual handling here.
- **The `ClinGen` validity path is partially wired.** `llm_service.py::format_clingen_data_for_llm` reads `common_genes_validity` from each prescription, but `analyze_prescriptions` currently only populates `common_genes` and `common_genes_scores` (Open Targets scores). Expect the ClinGen context to be empty unless that data is added upstream.
- **Auth is a single demo login.** `login_required` guards only the saved-results pages (`/results`, `/results/<id>`); analysis itself is public.
- **`render.yaml` runs `download_db.py` at build time.** The Google Drive `GDRIVE_FILE_ID` is hardcoded in that script — updating the local DB means re-uploading and changing that ID.
- `EXTERNAL_API_VERIFY_SSL` (env) toggles TLS verification for all outbound requests (Open Targets, Enrichr, UMLS, Gemini) — a single knob for restricted networks.
