# BAIonKM — Full App Bug/Breakage Audit

**Scope:** the deployed app (`main` branch).
**Method:** 7 review dimensions (routes/AI, analysis pipeline, frontend/JS, DB/migrations, external
integrations, live runtime smoke-test, config/security). Every reported bug was independently
adversarially verified before being counted. 47 agents total.

**Result: 11 confirmed issues — 0 critical · 2 high · 2 medium · 7 low.**
No critical bugs and no crashes in the core flows. The runtime smoke-test drove single/multi-disease
analysis, intersection/union/both + tabs, the AI poll cycle, autocomplete, history, and the DB
explorer — all worked. The findings are hardening, not broken features.

---

## 🔴 HIGH

### H1 — Stored DOM XSS: AI text rendered as HTML without escaping
- **Where:** `templates/result.html` — `formatMarkdown()` (~line 1948) does markdown→HTML via string
  `.replace()` and assigns directly to `innerHTML`, with **no HTML escaping**. Two sinks:
  `detailed_analysis` (~1694-1695) and clinical `rationale` (renderClinicalCards ~1903/1908).
- **What breaks:** the text is raw Gemini output. A model response containing
  `<img src=x onerror=alert(1)>` or `<svg onload=...>` executes JavaScript in the viewer's browser.
  It is **stored** (saved to `ai_analysis_json`, replayed on the login-gated `/results/<id>` page),
  and reachable beyond "if Google is compromised" because the user-controlled free-text disease/herb
  fields are injected into the Gemini prompt (prompt-injection → XSS). Note: the same function already
  escapes its *other* fields (`group_label`, `suspected_driver`, questions) via `escapeHtml()`, so this
  is an inconsistency, not a deliberate trusted-content decision.
- **Repro:** run an analysis that triggers AI; if the model emits a bare `<img onerror>`/`<svg onload>`
  in `detailed_analysis` or `rationale_hidden`, it runs on render (fresh and from history).
- **Fix:** escape HTML first, then apply the markdown formatting (or use DOMPurify). One fix covers
  H1 + M1 + M2. Apply to both `formatMarkdown` sinks.

### H2 — Public demo password committed to the repo
- **Where:** `config.py:112-113` — `DEMO_USERNAME='professor'`, `DEMO_PASSWORD='kiom2026'` as committed
  defaults. `render.yaml` does NOT override them (only `GEMINI_API_KEY`/`UMLS_API_KEY` are declared),
  so production runs on the public default password unless manually set in the Render dashboard.
- **What breaks:** anyone who reads the repo can log in → view ALL saved analyses (`/results`,
  `/api/results/history`) and DELETE any saved result (`DELETE /api/results/<id>`). `login_required`
  guards those endpoints, so the public creds are effectively unauthenticated access.
- **Repro:** `POST /login` with `professor` / `kiom2026` → `/results` and `DELETE /api/results/{id}`.
- **Fix:** remove the hardcoded default (`DEMO_PASSWORD = os.environ.get('DEMO_PASSWORD')`), fail-fast
  in production when unset, add `DEMO_USERNAME`/`DEMO_PASSWORD` to `render.yaml` as `sync:false`, and
  **rotate the now-public password** (set a new value in the Render dashboard — a secret the operator
  must set, not committed).

---

## 🟠 MEDIUM (same root cause as H1)

### M1 — XSS in `renderSummaryTable()`
- **Where:** `templates/result.html` ~1836-1863. AI `summary_table` cell values (line ~1856) AND
  column headers (line ~1848) are interpolated into an `innerHTML` string unescaped.
- **Fix:** wrap every `row[col]` and header `col` in the existing `escapeHtml()` helper.

### M2 — XSS in `renderClinicalCards()` via `rationale`
- **Where:** `templates/result.html` ~1903. `rationale` → `formatMarkdown()` → `innerHTML`, unescaped
  (same `formatMarkdown` root cause as H1). Note: a markdown-link payload does NOT trigger (no link
  parser); the working vector is a bare `<img onerror>`/`<svg onload>` in the model output.
- **Fix:** same sanitize-before-render as H1.

> **H1 + M1 + M2 are one coherent fix:** sanitize every AI-generated string before it touches
> `innerHTML` (escape-then-format, or DOMPurify). That closes all three.

---

## 🟡 LOW

### L1 — Negative `?page=` → 500 on Postgres
- **Where:** `routes.py:434` (`/api/database/herbs`, **public**) and `routes.py:1141`
  (`/api/results/history`, login-gated). Unlike `get_diseases_paginated` (which clamps `if page < 1`),
  these compute `.offset((page-1)*per_page)` with no lower bound.
- **What breaks:** a negative `page` yields a negative SQL `OFFSET`. SQLite tolerates it (returns
  first-page data, wrong); **Postgres (production) raises "OFFSET must not be negative" → unhandled
  500.** Also `per_page=0` → `ZeroDivisionError` in the `total_pages` computation.
- **Fix:** clamp in both endpoints: `if page < 1: page = 1` and `per_page = max(1, min(per_page, cap))`.

### L2 — Poll "absent" hides the real failure reason
- **Where:** `routes.py:~1485` (`ai_analysis_result`). On a Gemini failure, `generate_full_ai_analysis`
  computes a specific `error` string, but `_run_ai_generation` only saves on success, so the marker
  clears and the poll returns `{status:'absent'}` — the user sees a generic error, and the client
  wastes up to 2 extra Gemini retries. **Bounded** (`aiRetriggers < 2`), NOT infinite.
- **Fix:** persist a failure marker / return `{status:'failed', error:...}` so the poll surfaces the
  real reason and skips the wasted re-triggers.

### L3 — Venn drops diseases that returned 0 genes
- **Where:** `services.py:551` (`per_disease_sets` built with `if s:`) and `:565` (`_ds` filters
  `if r['scores']`). If you pick 3 diseases but one has no Open Targets genes, the Venn renders 2
  circles and the "intersection" is over the 2-with-data, while the label says "shared by all diseases."
- **What breaks:** label-vs-computation mismatch (a strict "shared by ALL" reading should be empty when
  any disease has zero genes). No crash; the existing "No genes found for disease: X" error partly
  signals it.
- **Fix:** include empty diseases as 0-size Venn regions (and let the all-disease intersection collapse
  to empty), or relabel as "shared by all diseases with gene data."

### L4 — No timeout on the AI status fetch
- **Where:** `result.html:~1658` (`checkAndRunAiAnalysis`) — `fetch('/api/ai-analysis/status')` has no
  `AbortController`/timeout, and the loading spinners are shown by default. If the network truly stalls
  (the endpoint itself is trivial and can't be "slow"), the spinner hangs forever.
- **Fix:** add an `AbortController` timeout (~10s) and handle `AbortError`.

### L5 — Gemini `MAX_TOKENS` truncation returns truncated JSON
- **Where:** `llm_service.py:55-59`. On a `finishReason == "MAX_TOKENS"` (default `maxOutputTokens`
  8192), it logs a warning but **returns the truncated text** instead of falling through to the next
  model. Truncated JSON fails `json.loads`; the re-ask reuses the same 8192 cap, so a genuinely large
  answer truncates again → `None` → empty AI result (graceful, no crash). Rare (needs >8192 output
  tokens).
- **Fix:** raise `maxOutputTokens`, and/or on `MAX_TOKENS` treat the result as unusable and fall
  through to the next model (change line 59 to `break`).

### L6 — Silent per-library Enrichr failure
- **Where:** `services.py:298-308` (`perform_enrichment_analysis_parallel`). If a user selects 2+
  libraries and one library's fetch fails, that task's rows are dropped silently (only a server print);
  the result header still advertises ALL requested libraries (`result.html:~1470` joins
  `results['enrichment_libraries']`). Only triggers with 2+ libraries (default is single DisGeNET).
- **Fix:** track failed `(prescription, library)` pairs and surface them in `results['errors']` + the UI.

### L7 — `SESSION_COOKIE_SECURE` defaults false
- **Where:** `config.py:23`; not set in `render.yaml`. Render terminates TLS / forces HTTPS, so impact
  is small (HttpOnly + SameSite=Lax are already set). Mostly a defense-in-depth gap.
- **Fix:** add `SESSION_COOKIE_SECURE: "true"` to `render.yaml`'s envVars.

---

## Recommended fix order
1. **The XSS trio (H1 + M1 + M2)** — one sanitization pass over all AI-rendered text. Most important
   (real stored XSS on a shared login).
2. **Demo creds (H2)** — code + `render.yaml`; the operator rotates the password in the Render dashboard.
3. **Quick low wins:** L1 (negative-page 500) and L7 (secure cookie) — two-line fixes worth bundling.
4. L2–L6 — optional polish.

## Also worth noting (from an earlier, separate review — not in this audit's 11)
- `services.py::_disease_tokens` keeps generic tokens (`"syndrome"`, `"disease"`), so
  `_clingen_validity_for` can falsely flag a gene as `disease_specific=True` for any "...syndrome"/
  "...disease" query — which also mis-colors the gene tags green ("validated for THIS disease"). Fix:
  require an exact MONDO/EFO id match or ≥2 shared non-generic tokens.
