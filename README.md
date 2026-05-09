# OmniAccountant

[![CI](https://github.com/KVM1L03/OmniAccountant/actions/workflows/ci.yml/badge.svg)](https://github.com/KVM1L03/OmniAccountant/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white)](https://nextjs.org/)
[![Temporal](https://img.shields.io/badge/Temporal-1.24-FF6F00?logo=temporal&logoColor=white)](https://temporal.io/)
[![DSPy](https://img.shields.io/badge/DSPy-3.x-blueviolet)](https://dspy.ai/)
[![Langfuse](https://img.shields.io/badge/Langfuse-v3-1f1f1f)](https://langfuse.com/)

> AI-powered invoice-to-ERP reconciliation. Durable workflows, structured LLM extraction, zero-trust ERP access, full LLM observability.

## Demo

[OmniAccountant.webm](https://github.com/user-attachments/assets/c72284a6-a576-44e6-8454-a99038d2c414)

---

## Table of contents

1. [Why this exists](#why-this-exists)
2. [Architecture](#architecture)
3. [Pipeline — one invoice end-to-end](#pipeline--one-invoice-end-to-end)
4. [Observability](#observability) — Langfuse, Temporal, OpenTelemetry
5. [Quick start](#quick-start)
6. [Configuration](#configuration)
7. [Step-by-step setup](#step-by-step-setup)
8. [Testing & CI](#testing--ci)
9. [Evaluation suite](#evaluation-suite)
10. [Project structure](#project-structure)
11. [Architectural invariants](#architectural-invariants)

---

## Why this exists

Enterprise AP teams burn thousands of hours each month cross-referencing supplier invoices against purchase orders. A swapped line item, an off-by-cents tax rounding, a vendor pricing drift — each one leaks revenue or surfaces an audit finding.

**OmniAccountant automates the loop end-to-end:**

| Stage | What it does |
|---|---|
| **Ingest** | Hot-folder pickup, dashboard upload, or batch trigger |
| **Extract** | DSPy-driven structured extraction — typed `InvoiceData` out, no prompt strings |
| **Reconcile** | LangGraph agent calls ERP via MCP tools (zero-trust boundary) |
| **Decide** | `APPROVED` · `DISCREPANCY` · `HUMAN_REVIEW_NEEDED` with reason + ERP delta |
| **Persist** | PostgreSQL audit trail; Langfuse trace per decision |

Every decision is **explainable** (traced), **durable** (Temporal-replayable), and **auditable** (MCP-bounded data access).

---

## Architecture

```mermaid
graph TB
    User([User])
    UI[Web Dashboard]
    API[API Gateway]
    WF[Workflow Engine]
    AI[AI Brain]
    ERP[(Company ERP)]
    DB[(History Database)]
    Watch[Monitoring]

    User --> UI
    UI --> API
    API --> WF
    WF --> AI
    AI --> ERP
    WF --> DB
    AI -.-> Watch
    WF -.-> Watch

    classDef user fill:#f1f5f9,stroke:#475569
    classDef app fill:#e0f2fe,stroke:#0284c7
    classDef ai fill:#fef3c7,stroke:#ca8a04
    classDef data fill:#fce7f3,stroke:#be185d
    classDef obs fill:#dcfce7,stroke:#16a34a
    class User user
    class UI,API,WF app
    class AI ai
    class ERP,DB data
    class Watch obs
```

**What each box does:**

| Box | Plain English | Code location |
|---|---|---|
| Web Dashboard | Where the user uploads invoices and sees results | `frontend/` |
| API Gateway | Receives uploads, kicks off processing | `api_gateway/` |
| Workflow Engine | Runs the work reliably — retries on failure, never loses an invoice mid-process | `ai_worker/workflows.py` |
| AI Brain | Reads the PDF, understands it, decides if it matches | `ai_worker/dspy_engine.py` + `ai_worker/agent_graph.py` |
| Company ERP | The source of truth — what each invoice *should* cost | `mcp_bridge/` (zero-trust gateway to the DB) |
| History Database | Stores every decision so you can audit it later | Postgres + Prisma |
| Monitoring | Records every AI call, cost, and workflow step | Langfuse + Temporal UI |

### Tech stack

| Layer | Choice | Rationale |
|---|---|---|
| **Frontend** | Next.js 16 · React 19 · Tailwind v4 · Prisma 7 | Server Actions = type-safe RPC; one binary for SSR + dashboard |
| **API gateway** | FastAPI · Pydantic v2 strict | Async I/O, OpenAPI docs free, strict mode kills coercion bugs |
| **Orchestration** | Temporal 1.24 | Durable execution + replay + automatic retries — non-negotiable for financial workflows |
| **LLM extraction** | DSPy 3.x | `Signature`-driven structured output; zero raw prompts in code |
| **Reconciliation agent** | LangGraph | Stateful tool-calling graph; clean separation from extraction |
| **ERP boundary** | MCP (FastMCP) | Single audit boundary; LLM agent cannot reach SQL directly |
| **LLM observability** | Langfuse v3 (self-hosted) + OpenInference + OTel | Cost, latency, prompt tracking — see [Observability](#observability) |
| **App DB** | PostgreSQL 16 + Prisma | Single shared container, three logical DBs (`temporal`, `invoice_app`, `langfuse`) |
| **Build** | `uv` (Python) · `npm` (Node) · Docker Compose | One-command bring-up; reproducible CI |

### Architectural highlights

- **Deterministic workflows.** All I/O is in Activities; Workflows replay byte-for-byte. No `datetime.now()`, no `random()`, no HTTP. See `ai_worker/workflows.py`.
- **Concurrency-safe LM access.** DSPy LMs are process-wide singletons (`threading.Lock`-guarded). Per-call scoping uses `dspy.context(lm=...)` to avoid global-state races when Temporal runs activities in parallel. See `ai_worker/llm_router.py`.
- **Zero-trust ERP.** The agent has no DB credentials. Every read goes through `@mcp.tool()` decorated functions in `mcp_bridge/server.py`, giving you a single chokepoint for audit + rate-limit + RLS.
- **Strict typing end-to-end.** `ConfigDict(strict=True)` on every Pydantic model; TypeScript `strict: true`; Prisma-generated types bridge the wire.
- **Schema isolation.** Three databases on one Postgres container — Temporal internals, app data, and Langfuse never collide.

---

## Pipeline — one invoice end-to-end

This is what happens when you drop a single PDF into the dashboard. Every arrow is a real interface boundary in the codebase.

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant App as Web App
    participant Worker as Workflow Engine
    participant AI as AI Brain
    participant ERP as Company ERP

    User->>App: Uploads invoice PDF
    App->>Worker: Start reconciliation
    Worker->>AI: Read this invoice
    AI-->>Worker: Invoice says 16,867.50
    Worker->>AI: Compare with ERP
    AI->>ERP: What should this cost?
    ERP-->>AI: Should be 16,817.50
    AI-->>Worker: Mismatch of 50.00
    Worker-->>App: DISCREPANCY found
    App-->>User: Shows result with reason
```

**In words:**

1. User uploads a PDF invoice.
2. The Workflow Engine takes over so nothing gets lost if the system restarts.
3. The AI reads the PDF and pulls out vendor, amount, invoice number.
4. The AI asks the company ERP: *"what should this invoice cost?"*
5. If the numbers match → **APPROVED**. If they don't → **DISCREPANCY** with the exact dollar gap. If anything looks suspicious → **HUMAN_REVIEW_NEEDED**.
6. Result lands back in the dashboard, and is permanently saved for audit.

If anything fails along the way (network blip, AI rate-limited, etc.), the Workflow Engine automatically retries from where it stopped — the user doesn't have to re-upload anything.

**Failure semantics:**

- LLM call fails (429, 5xx) → Temporal Activity retry policy fires; spans show every attempt in Langfuse
- MCP call fails → Activity fails; Temporal UI shows the exact tool call and stack
- DSPy returns malformed output → Pydantic strict mode rejects; activity surfaces a typed error
- Worker crashes mid-batch → Workflow resumes from last completed activity on next worker connect

---

## Observability

Two non-overlapping layers. **Don't conflate them** — they answer different questions.

```mermaid
graph LR
    AI[AI Brain] -->|sends every call| LF[Langfuse]
    WF[Workflow Engine] -->|sends every step| TUI[Temporal UI]

    LF --- LFNote[How much did the AI cost? What did it answer? Was it slow?]
    TUI --- TUINote[Did the workflow finish? Where is it stuck? Why did it retry?]

    classDef ai fill:#fef3c7,stroke:#ca8a04
    classDef wf fill:#dcfce7,stroke:#16a34a
    classDef note fill:#f8fafc,stroke:#cbd5e1,color:#475569
    class AI,LF ai
    class WF,TUI wf
    class LFNote,TUINote note
```

Both monitors run side-by-side — they answer different questions, neither replaces the other.

### Layer 1 — LLM observability via Langfuse

**What it answers:** "Which prompt did this generation see? How many tokens? How much did it cost? Was the model output what we expected? How does latency drift across the week?"

**Stack:** [OpenInference](https://github.com/Arize-ai/openinference) emits LLM-specific OTel span attributes (token counts, model name, prompt content). The OTel SDK ships them via OTLP/HTTP to Langfuse, which converts them into rich generations + traces with cost calculation and prompt linking.

**Wired up at:** `ai_worker/worker.py` — `get_client()` registers the global TracerProvider; then `DSPyInstrumentor().instrument()` and `LiteLLMInstrumentor().instrument()` patch the libraries to emit spans automatically.

**FinOps cost tracking gotcha (Vertex AI users):** Langfuse calculates cost by joining the trace's `model` attribute against its model-pricing table. LiteLLM emits the model as `vertex_ai/gemini-2.5-flash` (provider-prefixed), but Langfuse's seed pricing only ships entries without the prefix. **Tokens will record but cost will be `null`.** Fix in Langfuse UI → Settings → Models → Add custom model:

```text
Match pattern: ^(vertex_ai/)?gemini-2\.5-flash$
input price:   0.0000003   ($0.30 / 1M tokens)
output price:  0.0000025   ($2.50 / 1M tokens)
```

Langfuse recomputes cost only for **new** generations after this entry is saved. Old traces stay at $0.

**Where to look:**

| Question | URL | Path |
|---|---|---|
| Why did this invoice get DISCREPANCY? | http://localhost:3030 | Tracing → filter by `name:invoice_reconciliation` → click trace → expand DSPy span → see input PDF text + structured output |
| What's our daily LLM spend? | http://localhost:3000/reports | Frontend hits `/telemetry/finops` which aggregates `total_cost` from Langfuse traces |
| Which model is being used right now? | http://localhost:3030 | Any generation → "Provided model name" attribute |
| Did a prompt regress on a known input? | http://localhost:3030 | Datasets → Run → side-by-side diff |

### Layer 2 — Workflow observability via Temporal UI

**What it answers:** "Where in the workflow are we right now? Why did this activity retry? What input did Activity attempt #4 receive? Can I replay this workflow with patched code without re-running side effects?"

**This is not LLM-aware.** Temporal sees activities as opaque function calls. It cares about *durability* (every event is persisted), *determinism* (workflows replay deterministically from history), and *recovery* (worker crashes → next worker resumes).

**Where to look:**

| Question | URL | Path |
|---|---|---|
| Stuck batch — what's pending? | http://localhost:8085 | Workflows → Running → click the workflow → Pending Activities |
| Why did `process_invoice_activity` retry 3 times? | http://localhost:8085 | Activity → History tab → see exception traceback at each attempt |
| Replay a closed workflow with new code | http://localhost:8085 | Built-in replayer — no production-side state changes |

### Why both — and why not "just OpenTelemetry"

Langfuse v4 *is* OpenTelemetry. It's a thin layer on top of the official OTel SDK that adds LLM-specific aggregations (cost rollup, prompt versioning, generation-vs-span typing, eval datasets, model-pricing joins). Migrating to "vanilla OTel + Jaeger/Tempo" is a regression in this codebase: you'd lose token cost tracking, prompt management, and the FinOps dashboard endpoint that consumes `langfuse.api.trace.list`.

Temporal speaks gRPC, not OTel — it has its own event sourcing model where the workflow history *is* the trace. Forcing it into OTel would lose deterministic replay semantics, which is the whole reason Temporal is in this stack.

**Net:** keep the two-layer split. They're complementary, not redundant.

### Debug playbook

| Symptom | First thing to check | Then |
|---|---|---|
| Workflow stuck > 1 min | Temporal UI → Pending Activities | If LLM activity wedged: check Langfuse for the in-flight generation; check Vertex/OpenAI quota in cloud console |
| Cost shows $0 in `/reports` despite tokens recording | Langfuse model pricing table (see gotcha above) | If pricing is set and trace.total_cost is still null: bounce `api-gateway` (60s in-memory cache in `_telemetry_cache`) |
| LLM output schema validation error | Langfuse generation → "Output" tab — see the raw model output | Pydantic strict mode is rejecting it; check if the model returned natural language instead of JSON |
| Activity worked locally, fails in Docker | `make logs-vertex \| grep ai-worker` | Usually env var or service-account JSON mount issue |

---

## Quick start

**Vertex AI / Gemini Enterprise (recommended):**

```bash
cp .env.example .env                              # fill VERTEXAI_PROJECT
mkdir -p secrets
cp /path/to/service-account.json secrets/gcp-vertex-sa.json
make install
make seed                                          # ⚠️ MUST run before docker up
make up-build-vertex
make frontend                                      # in a second terminal
```

**Legacy API keys (OpenAI / Anthropic / Gemini API):**

```bash
make bootstrap     # install + seed + up-build + npm run dev
```

Open:

- Dashboard: http://localhost:3000
- Reports / FinOps: http://localhost:3000/reports
- Temporal UI: http://localhost:8085
- Langfuse: http://localhost:3030
- API docs: http://localhost:8000/docs

---

## Configuration

### Root `.env` (FastAPI + AI worker)

```bash
# LLM provider
LLM_PROVIDER=vertex_ai                             # or "api_keys"
VERTEXAI_PROJECT=your-gcp-project-id
VERTEXAI_LOCATION=europe-west4
# Optional model overrides — defaults to vertex_ai/gemini-2.5-flash both paths
# PRIMARY_LLM_MODEL=vertex_ai/gemini-2.5-flash
# FAST_LLM_MODEL=vertex_ai/gemini-2.5-flash

# When using mounted SA JSON instead of host ADC:
# GOOGLE_APPLICATION_CREDENTIALS=/var/secrets/google/gcp-vertex-sa.json

# Legacy keys (only when LLM_PROVIDER=api_keys)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...

# Langfuse client (project-scoped — generated in Langfuse UI on first login)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=http://localhost:3030

# Langfuse server (generate once with: openssl rand -hex 32)
LANGFUSE_NEXTAUTH_SECRET=...                       # Rotating invalidates sessions
LANGFUSE_SALT=...
LANGFUSE_ENCRYPTION_KEY=...                        # 64 hex chars exactly

TEMPORAL_ADDRESS=temporal:7233
```

### `frontend/.env.local` (Next.js + Prisma)

```bash
DATABASE_URL="postgresql://temporal:temporal@localhost:5432/invoice_app"
API_GATEWAY_URL="http://localhost:8000"
```

> Three databases on one Postgres container: `temporal` (workflow history), `invoice_app` (Prisma app schema), `langfuse` (observability metadata). The `langfuse` DB is created idempotently by `make up`'s `langfuse-db-create` target. Prisma's `db push` creates `invoice_app` on first run.

### Vertex AI authentication paths

| Context | How |
|---|---|
| Local Python (host) | `gcloud auth application-default login` then `gcloud config set project ...` |
| Local Docker | Mount SA JSON → `secrets/gcp-vertex-sa.json` → `make up-build-vertex` |
| Production | Workload Identity or runtime-bound SA — never JSON keys |

The SA needs `roles/aiplatform.user`. Add `roles/storage.*` only if you move invoices to GCS.

---

## Step-by-step setup

For when `make bootstrap` doesn't work and you need to debug.

### 1. Seed mock data (must come first)

```bash
make seed
```

Creates `mock_data/invoices/*.pdf` (3 matching, 2 with discrepancies) and `mcp_bridge/erp_mock.db` with corresponding PO rows.

> ⚠️ The `ai-worker` container bind-mounts `mcp_bridge/erp_mock.db`. If the file doesn't exist on the host first, Docker creates it as a *directory* and the worker fails on `aiosqlite.connect(...)`.

### 2. Start the stack

```bash
make up-build-vertex          # Vertex SA path
# or
make up-build                 # Legacy API-key path
```

Brings up: `postgres`, `temporal` + `temporal-ui` + `temporal-admin-setup`, `api-gateway`, `ai-worker`, `langfuse` + `langfuse-worker`, `clickhouse`, `redis`, `minio` + `minio-setup`. Wait ~30s for migrations.

```bash
make ps-vertex && curl -I http://localhost:8000/docs
```

All containers should be `Up (healthy)`.

### 3. Bootstrap Langfuse (one-time)

1. http://localhost:3030 → create admin account (sign-up disables itself after first user)
2. Create project → copy public + secret keys → paste into `.env`
3. Add Vertex model pricing (see [Observability gotcha](#layer-1--llm-observability-via-langfuse))
4. `docker compose restart api-gateway ai-worker`

### 4. Start the frontend

```bash
make frontend
```

Equivalent to:
```bash
cd frontend
npx prisma db push && npx prisma generate
npm run dev
```

### 5. End-to-end smoke test

1. http://localhost:3000 → Select PDFs → upload from `mock_data/invoices/`
2. Click **Scan & Process Directory**
3. Status badge transitions `RUNNING` → `COMPLETED`
4. Refresh — see persisted result in **Recent Batch Results**
5. Cross-check: http://localhost:8085 (Temporal workflow), http://localhost:3030 (Langfuse trace), http://localhost:3000/reports (FinOps cost rollup)

---

## Testing & CI

GitHub Actions runs three independent jobs on every push and PR to `main`:

| Job | Command (mirrors locally) |
|---|---|
| **python-lint** | `uv run ruff check .` |
| **python-test** | `uv run pytest tests/ --cov=. --cov-report=xml` |
| **frontend-lint** | `cd frontend && npm run lint` |

Pipeline: [`.github/workflows/ci.yml`](./.github/workflows/ci.yml).

Run all three locally before pushing:

```bash
uv run ruff check .
uv run pytest tests/
cd frontend && npm run lint
```

Pytest's `tests/conftest.py` autouse fixture seeds `mcp_bridge/erp_mock.db` so tests work in CI without `make seed` (the DB file is gitignored).

---

## Evaluation suite

Two layers, both designed to run with **zero LLM cost** by default.

### Promptfoo — extraction accuracy

Config: [`promptfooconfig.yaml`](./promptfooconfig.yaml). Provider is `evals/mock_dspy_provider.py` — a Python function that pattern-matches invoice IDs in fixture text and returns pre-baked `InvoiceData` JSON. Zero network calls.

```bash
npx promptfoo eval && npx promptfoo view
```

Asserts JSON validity, exact-match on `invoice_id`/`vendor_name`/`total_amount`, and a prompt-injection guard (a fixture with `[Ignore previous instructions...]` embedded in the vendor line — output must not contain `"hacked"` or alter the amount).

### LLM-as-judge — decision verification

Script: [`evals/llm_judge_evals.py`](./evals/llm_judge_evals.py). Verifies whether a `ReconciliationDecision` is correct given the stated and ERP-expected amounts.

```bash
EVAL_DRY_RUN=1 uv run python evals/llm_judge_evals.py        # zero-cost, business-rule verdict
JUDGE_MODEL=claude-haiku-4-5-20251001 uv run python evals/llm_judge_evals.py   # ~$0.001/run
```

Dry-run mode computes the verdict deterministically from `|stated - expected| < 0.01`. The live mode uses Claude Haiku via litellm with `num_retries=3`.

---

## Project structure

```
.
├── api_gateway/             # FastAPI HTTP layer
│   └── main.py              # Upload, batch trigger, /telemetry/finops
├── ai_worker/               # Temporal worker
│   ├── workflows.py         # Deterministic batch workflow
│   ├── activities.py        # Side-effecting activities
│   ├── dspy_engine.py       # Structured invoice extraction
│   ├── agent_graph.py       # LangGraph reconciliation agent
│   ├── llm_router.py        # Thread-safe LM singleton
│   └── worker.py            # Entrypoint + OpenInference instrumentation
├── mcp_bridge/              # Zero-trust ERP boundary
│   ├── server.py            # FastMCP server
│   └── init_db.py           # SQLite bootstrap
├── shared/
│   ├── schemas.py           # InvoiceData, ReconciliationDecision, FinOpsDailyPoint
│   └── pdf_utils.py         # Sandboxed PyMuPDF text extraction
├── frontend/                # Next.js 16
│   ├── src/app/
│   │   ├── page.tsx         # Dashboard
│   │   ├── reports/page.tsx # FinOps + telemetry
│   │   └── actions.ts       # Server Actions
│   ├── src/lib/format.ts    # Adaptive USD formatter (handles sub-dollar costs)
│   └── prisma/schema.prisma # Batch + Invoice models
├── evals/                   # Eval suite
│   ├── mock_dspy_provider.py
│   ├── llm_judge_evals.py
│   └── fixtures/
├── promptfooconfig.yaml     # Promptfoo entrypoint
├── tests/                   # Pytest — LLM router, DSPy, MCP server
├── .github/workflows/ci.yml # CI pipeline
├── docker-compose.yml
├── docker-compose.vertex.example.yml
├── seed_data.py             # ⚠️ Run first
└── pyproject.toml
```

---

## Architectural invariants

These are not style preferences — they are correctness guarantees. Violations break replay, audit, or concurrency.

1. **Microservices boundary.** `api_gateway`, `ai_worker`, `mcp_bridge` are separate processes. Never collapse them.
2. **Workflows are deterministic.** No `datetime.now()`, `random()`, `time.sleep()`, or HTTP calls inside `@workflow.defn`. All side effects → activities. Use `workflow.now()`, `workflow.sleep()` if needed.
3. **No prompt strings.** Extraction goes through `dspy.Signature`. No LangChain prompt templates. No f-strings building model inputs.
4. **Pydantic strict mode.** Every cross-process schema has `model_config = ConfigDict(strict=True)`.
5. **Zero-trust data.** The agent has no DB connection string. ERP reads/writes go through `@mcp.tool()` exclusively.
6. **LM singletons.** `dspy.LM` instances are process-wide singletons guarded by `threading.Lock`. Never call `dspy.configure()` — use `dspy.context(lm=...)` per-call instead.

Full contributor guide: [`CLAUDE.md`](./CLAUDE.md).

---

## License

MIT.
