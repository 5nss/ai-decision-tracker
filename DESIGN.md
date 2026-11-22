# DESIGN: Hindsight

> v2 of ai-decision-tracker. v1 used keyword heuristics and a single Gemini prompt, and it's preserved in git history.
> This doc covers what the system does, how a request flows through it, what can go wrong, and how we know it works.

## 1. Problem

People rarely learn from their decisions. They forget why they made them, and hindsight bias rewrites the memory ("I knew it wouldn't work"). **Hindsight locks your reasoning at decision time, makes you put a probability on it, and grades you when the outcome arrives.** You get two kinds of feedback:

- **Calibration.** When you say you're 80% sure, how often are you right? This is measured with a Brier score and a reliability chart.
- **Assumption audit.** An LLM pulls out the assumptions your decision rests on. After the outcome, it judges which ones held or failed and quotes what happened as evidence. Failures are grouped into patterns, for example "time assumptions fail 63% of the time."

Value starts with the first decision, because the audit and pre-mortem run immediately. It grows with every review.

**Users.** Students and early-career engineers making career, study and project decisions. A second audience is a reviewer of this repo: the demo workspace ships with a populated six-month journal, so the app is never empty on first launch.

## 2. Components

| Component | Job |
|---|---|
| **React SPA** (Vite, TypeScript, Tailwind) | Log decisions, review outcomes, dashboard, eval report, LLM traces |
| **FastAPI API** | REST endpoints, validation, workspace scoping (`X-Workspace` header) |
| **Auditor** (`hindsight/ai`) | One interface with two implementations. `GeminiAuditor` uses structured JSON outputs and embeddings. `HeuristicAuditor` is the offline, no-key mode and also the eval baseline. |
| **Retrieval** | Cosine top-k over decision embeddings stored in SQLite |
| **Insights** | Calibration (Brier score, skill score, reliability bins, trend) and assumption-failure patterns ranked by Wilson lower bound |
| **Tracing** | Every model call writes a row to `llm_calls`: operation, model, latency, tokens, error |
| **Eval harness** (`backend/evals`) | Gold dataset and metrics. Compares the baseline against Gemini on extraction, verdicts and retrieval. |
| **SQLite** | All data in one file. SQLAlchemy keeps Postgres one URL change away. |

## 3. Data flow

### Logging a decision: `POST /api/decisions`
1. The user submits a title, reasoning, alternatives, expected outcome, confidence (50–99%), domain and review date.
2. The API validates the input and saves the row. `created_at` is set by the server, so clients cannot backdate. Decision text is immutable after this point.
3. The auditor embeds `title + reasoning + expected outcome` and stores the vector on the row, tagged with the embedding model's name.
4. Retrieval finds the top 3 most similar **reviewed** decisions in the same workspace that were created before this one, keeping only those with cosine ≥ the model's threshold. Each comes with its failed assumptions.
5. The auditor calls Gemini with the decision plus those past cases and asks for JSON matching `AuditResult`:
   - up to 5 assumptions, each with text, category and risk
   - missing considerations
   - a one-line pre-mortem
   - repeat warnings that cite a past decision ID when an assumption echoes one that failed before
6. The results are saved and `audit_status` becomes `done`. **If any step fails, the decision is still saved** with `audit_status = failed`, the error is recorded, and the UI shows a retry button.

### Recording an outcome: `POST /api/decisions/{id}/outcome`
1. The user answers "Did your expected outcome happen?" (yes or no) and writes what happened.
2. The outcome is saved. There's one per decision, so a second one returns 409.
3. The auditor judges each assumption as `held`, `failed` or `unclear`. It must quote the outcome text as evidence and writes a one-line lesson.
4. A **grounding check** confirms each evidence quote actually appears in the outcome text. Quotes that don't are flagged as ungrounded in the UI.
5. Calibration and patterns are **computed on read** from these rows. There's no cached "behavior" table to go stale, which was a v1 bug.

## 4. Data

| Table | Key columns |
|---|---|
| `decisions` | id, workspace, title, reasoning, alternatives, expected_outcome, confidence (0.5–0.99), domain, review_at, created_at (server), audit_status/error, premortem, missing_considerations (JSON), repeat_warnings (JSON), embedding (float32 BLOB), embedding_model |
| `assumptions` | id, decision_id, text, category (`time`, `self`, `people`, `money`, `external`, `other`), risk (`low`, `medium`, `high`), verdict (`held`, `failed`, `unclear`, or null until review), evidence, evidence_grounded |
| `outcomes` | id, decision_id (unique), happened (bool), what_happened, lesson, review_status/error, created_at |
| `llm_calls` | id, created_at, operation (`audit`, `review`, `embed`), provider, model, latency_ms, input_tokens, output_tokens, ok, error, decision_id |

Workspaces: `demo` (seeded and resettable) and `personal`. The demo journal is `hindsight/seed/demo_journal.json`: 36 hand-labeled decisions that also serve as the eval gold set.

## 5. Failure cases

1. **Gemini is down, rate-limited or slow.** Each call has a timeout and 2 retries with exponential backoff on 429, 5xx and network errors. After that, `audit_status = failed`, the decision is kept and can be retried, and the trace row records the error.
2. **The model returns JSON that doesn't match the schema.** It gets one retry, then fails cleanly. Partial results are never saved.
3. **There's no API key.** The app runs in offline mode on `HeuristicAuditor` and the UI shows an offline badge. The demo workspace still works fully.
4. **Cold start.** With fewer than 5 reviewed decisions, calibration is shown with a "small sample" warning. A pattern needs at least 3 judged assumptions in its category. The Wilson bound keeps "2 of 2 failed" from reading as 100%.
5. **Retrieval returns irrelevant cases.** A per-model similarity threshold means no "similar decisions" are shown rather than wrong ones.
6. **The model invents evidence.** The grounding check flags quotes that aren't in the user's own outcome text.
7. **The embedding model changes**, for example a key is added later. Vectors are tagged with their model, and on startup anything embedded with a different model is re-embedded.

## 6. How I'll know it works

- **Unit and API tests** (pytest, no network) cover calibration math, the Wilson bound, retrieval, heuristics, retry and error handling with a fake Gemini client, and the full API flow on the offline auditor.
- **Evals** on 30 reviewed, hand-labeled decisions (synthetic, written for this project):

  | Eval | Metric | Baseline |
  |---|---|---|
  | Assumption extraction | precision, recall, F1 (semantic matching) | cue-word heuristic (v1's approach, substring bug fixed) |
  | Assumption verdicts | accuracy, macro-F1, confusion matrix | keyword negation heuristic |
  | Similar-decision retrieval | recall@3, MRR | v1's same-domain-most-recent rule, and lexical TF-IDF |

  Results go to `backend/evals/results/latest.json`, render on the **Evals** page, and are summarized in the README.
- **Traces**: p50 and p95 latency, error rate and token use per operation, shown on the Traces page.

## 7. Decisions and trade-offs

- **No vector database.** A few hundred decisions × 768 floats is under 1 MB, and numpy cosine over that takes milliseconds. A vector DB would be over-engineering at this scale. Revisit at around 100k rows.
- **SQLite instead of Postgres.** The app is single-user and local-first. The ORM keeps migration trivial.
- **Synchronous audit inside the request.** A 2–6 s wait is fine for a deliberate action, and it avoids a job queue plus polling. Revisit if audits get slower.
- **Immutable decisions.** The product's value depends on honest past reasoning, so there's no edit endpoint.
- **Binary outcomes.** The Brier score needs yes or no. Nuance goes in the free-text notes.
- **The offline mode is the baseline.** It implements the same interface, so the eval compares like with like.
- **Model as config.** The default is the `gemini-flash-latest` alias. Traces and eval reports record the exact model version the API returned, so results stay reproducible.

## 8. Non-goals

- Accounts and auth. It's a single-user local app, and workspaces separate demo data from real data.
- Reminders and notifications. A "due for review" queue in the UI covers this.
- Fine-tuning, or any model training.
