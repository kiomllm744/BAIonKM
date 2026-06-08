# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Flask web app (BAIonKM) for traditional Chinese medicine (TCM) mechanism-of-action research. A user enters **up to 3 diseases** and **up to 2 prescriptions** (lists of herbs); the app resolves each disease to an Open Targets ID, fetches **all** disease-associated genes, finds which of those genes each prescription's herbs target (the **common** genes), runs pathway enrichment on the common genes, and optionally generates an LLM-written comparative analysis. With 2+ diseases the user first chooses how to combine their genes — **union, intersection, or both** — on a dedicated choice screen. Used to hypothesize mechanisms of action for herbal formulas against disease(s).

## Commands

```powershell
# Setup (Windows; .venv is already present). On macOS, double-click run.command (it
# creates the venv, installs deps, downloads the DB, builds indexes, and launches).
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python download_db.py            # fetches diseaseportal.db from a GitHub Release asset (gitignored, too large for git)
python build_disease_index.py    # builds the local `diseases` autocomplete catalogue from an Open Targets parquet (idempotent)

# Run locally — http://localhost:5000 (honors the PORT env; macOS AirPlay holds 5000,
# so run.command / the preview fall back to another port). Debug on unless FLASK_ENV=production.
python app.py

# Production (Render / Procfile)
gunicorn app:app --bind 0.0.0.0:$PORT
```

There is **no test suite, linter, or build step**. Verify changes by running the app (or `app.test_client()` for a quick server-side render check).

Required environment (local: `.env`; prod: Render dashboard, `sync: false` keys in `render.yaml`):
- `GEMINI_API_KEY` — without it analysis still works but the AI-analysis endpoint returns 503.
- `UMLS_API_KEY` — optional; without it the UMLS terminology step is silently skipped (Open Targets still works).
- `SECRET_KEY` — **set it.** The fallback is per-process random, which breaks sessions across the two gunicorn workers (and `/result` is session-based).
- `DATABASE_URL` (Postgres in prod; `postgres://` auto-rewritten to `postgresql://` in `config.py`), `DEMO_USERNAME`/`DEMO_PASSWORD`.
- `ENRICHMENT_LIBRARIES` — comma-separated Enrichr library names; **default is `DisGeNET`**. Chosen per request via the top-bar "Libraries" picker.
- `EXTERNAL_API_VERIFY_SSL` — single TLS-verify toggle for ALL outbound calls (must be true in prod).

## Architecture

### Two data sources, deliberately split
- **Local DB** holds `herbs` (~437 herbs from BATMAN-TCM: herb → compound → target-gene), the `diseases` autocomplete catalogue (built by `build_disease_index.py`), and optionally `clingen_validity` (built by `build_clingen_index.py` when its source data is available). The DB file is downloaded by `download_db.py` from a **GitHub Release asset** (not Google Drive). `Config.SQLALCHEMY_DATABASE_URI` defaults to local `diseaseportal.db`.
- **Disease genes/scores are always live from Open Targets** (GraphQL, `opentargets_service.py`) — never stored locally beyond caching.

### The analysis pipeline (`services.py::analyze_prescriptions(..., disease_gene_mode='union')`)
1. **Resolve each disease → Open Targets ID** (`resolve_disease_to_open_targets`): a raw `EFO_*`/`MONDO_*`/`Orphanet_*` bypasses; else an exact local-catalogue match; else UMLS `candidate_names_for_open_targets` (raw input first, then standardized names), each tried against Open Targets search until one resolves (first hit wins). `match_source` records who resolved it. **UMLS is only a terminology bridge — Open Targets is the source of truth for IDs, genes, scores.**
2. **Fetch ALL associated genes + scores** (`fetch_live_associated_genes(efo_id, limit=None)`) — no 300 cap; pages of 2000 fetched concurrently via `ThreadPoolExecutor`. Plus evidence datatypes (still capped at 300) and the uncapped target count.
3. **Cross-disease aggregation + mode:** both `union_genes` (all) and `shared_core` (∩ across diseases) are computed; `disease_gene_mode` (`union` | `intersection`) selects which set drives the run. Intersection with no shared genes → friendly early return (still shows the disease Venn).
4. **Per prescription, batch-query `herbs`** for the union of target genes (one lowercase `IN (...)` query per prescription, not per herb). Missing herbs reported as `missing_herbs`.
5. **Set math:** `common_genes` = disease-gene set ∩ herb genes; distinctive = a prescription's common genes not common to the other. Common genes are ordered by **ClinGen validity group, then Open Targets score**.
6. **Enrichment runs on the COMMON genes** (prescriptions with ≥`MIN_ENRICHMENT_GENES`=3) — uploaded to Enrichr and scored against the selected libraries (default `DisGeNET`; KEGG/Reactome/GO/WikiPathways optional), adjusted p < 0.05, top 15. Upload + fetch run in parallel via `ThreadPoolExecutor`.
7. Result saved as one `AnalysisResult` row; `both` mode runs the pipeline twice and stores `{both:True, modes:{union, intersection}}`. PRG: id stashed in `session['last_result_id']` → 303 redirect to `/result`.

### Choice screen + result tabs
With 2+ diseases and no chosen mode, `/analyze` renders **`choose_mode.html`** (disease-overlap Venn + union/intersection/both buttons) which re-POSTs a **byte-identical** hidden form + `disease_gene_mode` (don't reformat the echoed `form_diseases`/`form_herbs`/per-lib hidden inputs). A `both` result shows `?tab=union|intersection` tabs in `result.html`. All Venn diagrams are collapsible (collapsed by default, `.viz-toggle`).

### AI analysis is a separate, client-triggered BACKGROUND pass
On result load, `result.html` JS rebuilds `prescription_enrichments` and POSTs `/api/ai-analysis` with `result_id`, `mode`, and the UI `language`. The route claims `(result_id, mode)` in the **`ai_inflight` DB table** (atomic across gunicorn workers), spawns a **daemon thread**, returns 202, and the client polls `/api/ai-analysis/result`. The thread calls `llm_service.py::generate_full_ai_analysis` → `get_gemini_json`/`get_gemini_response` (model `gemini-3.5-flash` + a fallback chain, retries) for strict-JSON `summary_table` + `detailed_analysis` + `clinical_questions`. `_language_directive` makes Gemini write **Korean values with English JSON keys** when the UI is Korean. Output is saved **mode-keyed** onto `ai_analysis_json` (merged, so a `both` row keeps both tabs). LLM responses are defensively parsed (`extract_json_from_response`).

### Caching
`external_lookup_cache` — one table, many `provider` prefixes. Open Targets: plaintext keys, 15-day TTL; **uncapped vs capped gene fetches use different providers** (`opentargets_genes_full` vs `opentargets_genes`); separate providers for count/datatypes/suggest/search/meta. UMLS: sha256 keys, `UMLS_CACHE_TTL_DAYS`. Don't assume one keying scheme.

### Routes (`routes.py`, one `main_bp` blueprint)
- `POST /analyze` — pipeline entry (runs union for ≤1 disease, else renders `choose_mode.html`, else runs the chosen mode/both). PUBLIC.
- `GET /result` — PRG target; reads `session['last_result_id']` (not a URL id). PUBLIC, non-enumerable. `GET /results/<id>` + the history APIs are LOGIN-REQUIRED.
- `POST /api/ai-analysis` (background job) + `GET /api/ai-analysis/result` (poll) + `GET /api/ai-analysis/status`.
- `GET /api/diseases` — local-catalogue-first autocomplete (`_local_disease_match` + `_relevance_score`), UMLS bridge for abbreviations/sparse hits, typo fallback, `_blend_open_targets_relevance` (re-rank by OT relevance + `looks_like_disease` filter), `_umls_open_targets_bridge` (last-resort exact resolution for lay phrases like "tummy ache"→dyspepsia), and a live-OT fallback filtered by `_is_relevant_open_targets_suggestion`.
- `GET /api/resolve-trace` — reports the real resolution (`match_source`, efo_id, candidates).
- `GET /api/herbs`, `/api/herbs/validate` — **bilingual** (Korean Hangul or English/Pinyin) via `herb_mappings.py`.
- `GET /api/database/*` (A→Z disease browse), `/api/stats`, `/api/provenance`, `/api/translate-symptoms`.

### Frontend / i18n
No Jinja base layout — every page includes `partials/_head_i18n.html` + `partials/_topbar.html`. Client-side i18n in `static/js/i18n.js` (**default language Korean**, `localStorage baionkm.lang`); static text uses `data-i18n*` attributes, JS-generated DOM re-renders on the `langchange` event (listener in `app.js`). **New strings need BOTH `en` and `ko` tables.** The top bar holds the enrichment-**library picker** (`#lib-picker`, persisted, injected into the analysis form as hidden `enrichment_libraries` inputs on submit; empty → server default DisGeNET). The analysis form has exactly **2 fixed prescription cards** (no Add button) and **up to 3 disease chips**, with quick-test prescription presets and quick-add default-disease presets.

## Conventions and gotchas specific to this repo

- **Engines are per-module, not shared.** `routes.py`, `services.py`, `opentargets_service.py`, `umls_service.py` each call `create_engine(...)` + `sessionmaker(...)`. flask-sqlalchemy's `db` is essentially only for model definitions. Follow the local `Session()` + `try/finally: session.close()` pattern.
- **Schema migration is hand-rolled at import time.** `routes.py::init_results_table()` (module-level call) creates/`ALTER`s `analysis_results` (incl. `ai_analysis_json`), `external_lookup_cache`, and `ai_inflight` — outside any app context, no Alembic. `herbs`/`diseases`/`clingen_validity` ship in the downloaded DB and are NOT created here.
- **`ai_inflight` must stay a DB table** with composite PK `(result_id, mode)` — that atomic INSERT is what makes the in-flight claim work across the two gunicorn workers. Reverting to an in-memory set re-introduces a prod bug (polls on a different worker falsely report "absent").
- **The AI blob is mode-keyed** (`{union:{...}, intersection:{...}}`; legacy bare blobs are also tolerated) and the save path **merges** (don't clobber the other tab). `mode` is clamped to union|intersection (passing `both` coerces to union).
- **Enrichment runs on COMMON genes** (not unique). The `summary_table` has two shapes — multi-Rx: `Feature` + dynamic `Group N`; single-Rx: `Feature` + `Finding` — the renderer tolerates both; to drop a row you edit the prompt (no post-filter).
- **ClinGen validity is mostly inert** unless the `clingen_validity` table is present; `format_clingen_data_for_llm` gates the LLM ClinGen block on the literal string "Official ClinGen matches found".
- **`/result` is session-based** (public, non-enumerable); `/results/<id>` (login) is the durable view. `login_required` guards only `/results*` + history APIs; `/analyze`, `/result`, and all autocomplete/database/AI APIs are PUBLIC.
- **`download_db.py` pulls the DB from a GitHub Release asset** — updating the local DB means publishing a new release asset and pointing the script at it. `render.yaml` runs `download_db.py` + the index builders at build (the builders are `|| true`, so a build failure silently falls back to live Open Targets search with no local catalogue).
- **`EXTERNAL_API_VERIFY_SSL`** toggles TLS verification for ALL outbound requests (Open Targets, Enrichr, UMLS, Gemini, and `download_db.py`). Must be true in prod.
- **Default language is Korean.** New dynamic strings need both `en`/`ko`; static text needs `data-i18n*`; JS-built DOM must re-render in the `langchange` listener. The body is cloaked until i18n runs — beware layout-measuring inline scripts.
- **A dev machine may have two checkouts:** the git clone (e.g. `~/Projects/Disease_Portal`, the source of truth → GitHub → Render) and an older Google-Drive copy. Always edit/commit in the **git clone**; the Drive copy is stale.
