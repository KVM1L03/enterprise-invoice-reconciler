# OmniAccountant

## 🔴 Demo

[OmniAccountant.webm](https://github.com/user-attachments/assets/c72284a6-a576-44e6-8454-a99038d2c414)

> **Production-grade, AI-powered B2B platform that automates invoice-to-ERP matching using LLMs, durable workflows, and a zero-trust data integration layer.**

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white)](https://nextjs.org/)
[![Temporal](https://img.shields.io/badge/Temporal-Workflows-FF6F00?logo=temporal&logoColor=white)](https://temporal.io/)
[![DSPy](https://img.shields.io/badge/DSPy-LLM-blueviolet)](https://dspy.ai/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)

---

## 💡 The Business Problem

Enterprise finance teams burn thousands of hours every month manually cross-referencing supplier invoices against purchase orders in their ERP systems. A single discrepancy — a swapped line item, an incorrect tax rate, a vendor pricing drift — can leak revenue and trigger audit findings.

**This platform automates the entire reconciliation loop:**

- 📥 **Ingest** PDF invoices from email, hot folders, or direct upload
- 🧠 **Extract** structured data (vendor, line items, totals, tax) using LLMs with type-safe outputs
- 🔍 **Reconcile** each invoice against the ERP's expected purchase order data via a secure tool-calling agent
- ⚖️ **Decide** with full audit trail: `APPROVED`, `DISCREPANCY`, or `HUMAN_REVIEW_NEEDED`
- 📊 **Persist** every decision so finance ops can review history, drill into outliers, and prove compliance

The result: **manual audit time drops from hours per invoice to seconds**, while every decision remains explainable, durable, and observable.

---

## 🏛️ Architecture

The system is a **distributed microservices architecture** with strict separation of concerns. Each layer is independently scalable and uses durable execution where state matters.

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Next.js Dashboard (Frontend)                      │
│         React 19 · Tailwind v4 · Prisma ORM · Server Actions          │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ HTTP + RPC (Server Actions)
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   FastAPI Gateway (api_gateway/)                      │
│             Async upload · Workflow trigger · Status polling          │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ Temporal gRPC
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│              Temporal Workflow Orchestration (ai_worker/)             │
│  Deterministic batch workflow · Parallel activities · Retry policies  │
│                                                                       │
│   Phase 1: process_invoice_activity  (DSPy + LangGraph + MCP)         │
│   Phase 2: route_invoice_file_activity (hot-folder routing)           │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ MCP tool calls (stdio)
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│              MCP Bridge — Zero-Trust ERP Layer (mcp_bridge/)          │
│       FastMCP server · SQLite ERP mock · Tool-call audit boundary     │
└──────────────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Frontend** | Next.js 16 · React 19 · Tailwind CSS v4 · Prisma ORM 7 | Server Actions for type-safe RPC, persistent reconciliation history |
| **API Gateway** | FastAPI · Pydantic v2 (strict mode) · Uvicorn | Async HTTP, strict type contracts, OpenAPI auto-docs |
| **Orchestration** | Temporal.io | Durable execution, automatic retries, workflow replay, deterministic guarantees |
| **AI Engine** | DSPy · LangGraph · PyMuPDF · Langfuse (self-hosted) | Structured LLM extraction (no prompt strings), agentic decision graph, PDF text extraction, full LLM observability |
| **ERP Integration** | Model Context Protocol (FastMCP) · SQLite | Zero-trust tool boundary — the LLM agent can only touch the ERP through audited MCP calls |
| **Application DB** | PostgreSQL 16 · Prisma ORM | Persistent batch history, KPI aggregation, schema-isolated from Temporal internals |
| **Infrastructure** | Docker Compose · `uv` (Python) · `npm` (Node) | One-command bring-up, reproducible builds |

### Architectural Highlights

- **🔒 Zero-trust ERP access:** Direct database connections from the AI agent are forbidden. Every read/write goes through the MCP bridge, which becomes the single auditable choke point for compliance.
- **♻️ Deterministic workflows:** Temporal workflows contain zero I/O — all side effects live in activities. This makes them replay-safe and observable in the Temporal UI.
- **🧩 Strict typing end-to-end:** Pydantic v2 (`ConfigDict(strict=True)`) on the Python side, TypeScript `strict: true` on the frontend, and Prisma-generated types bridge the gap.
- **⚡ Concurrency-safe LLM access:** DSPy LMs are process-wide singletons; per-call scoping uses `dspy.context(lm=...)` to avoid race conditions during parallel activity execution.
- **📦 Schema isolation:** Prisma uses a dedicated `app` PostgreSQL schema in the same container as Temporal — zero collision, one container.

---

## 🚀 Getting Started

### Prerequisites

You'll need the following installed on your machine:

- 🐳 **Docker** & **Docker Compose** — for the backend stack (Postgres, Temporal, FastAPI, AI worker)
- 📦 **[uv](https://github.com/astral-sh/uv)** — fast Python package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- 🟢 **Node.js 20+** & **npm** — for the Next.js frontend
- 🔑 An LLM API key (OpenAI, Anthropic, or Google Gemini)

---

## ⚡ Quick Start (TL;DR)

**Fresh clone — one command:**

```bash
cp .env.example .env    # then paste your LLM API key(s)
make bootstrap
```

`make bootstrap` runs `install` → `seed` → `up-build` → `npm run dev` in sequence:
1. Installs all dependencies (`uv sync`, `npm ci`)
2. Seeds mock data (`seed_data.py` — generates PDFs + `erp_mock.db`)
3. Brings up the full Docker stack (Temporal, Postgres, FastAPI, AI worker, Langfuse + its deps)
4. Starts the Next.js dev server in the foreground

**Subsequent runs** — deps and seed are already in place:

```bash
make dev
```

Then open:
- **Dashboard:** http://localhost:3000
- **Temporal UI:** http://localhost:8085
- **API Docs:** http://localhost:8000/docs
- **Langfuse:** http://localhost:3030

---

## 📖 Step-by-step setup (if you prefer manual control)

### Step 1 — Configure environment variables

Create a `.env` file in the **project root** (used by FastAPI and the AI worker via Docker `env_file`):

```bash
# LLM Provider (at least one is required)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...

# LLM Observability — self-hosted Langfuse (docker-compose runs it on port 3030)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=http://langfuse:3000

# Langfuse container secrets (generate each with: openssl rand -hex 32)
LANGFUSE_NEXTAUTH_SECRET=<openssl rand -hex 32>
LANGFUSE_SALT=<openssl rand -hex 32>
LANGFUSE_ENCRYPTION_KEY=<64 hex chars>

# Temporal (defaults to host networking)
TEMPORAL_ADDRESS=temporal:7233
```

Create `frontend/.env.local` for Prisma to reach Postgres (the same container Temporal uses, but in a dedicated database):

```bash
DATABASE_URL="postgresql://temporal:temporal@localhost:5432/invoice_app"
API_GATEWAY_URL="http://localhost:8000"
```

> 💡 `invoice_app` is a separate database on the shared Postgres container (distinct from Temporal's `temporal` DB and Langfuse's `langfuse` DB). Prisma 7's `db push` creates it automatically on first run using the `createdb` grant that the `temporal` user has — no manual SQL required.

---

### Step 2 — Install dependencies

```bash
make install
```

Or manually:

```bash
uv sync
cd frontend && npm ci
```

---

### Step 3 — Seed the data ⚠️ **(Critical!)**

Generate the mock invoices and seed the ERP database:

```bash
make seed
```

Or manually:

```bash
uv run python seed_data.py
```

This script:
- Creates **5 sample PDFs** in `mock_data/invoices/` (3 matching, 2 with discrepancies)
- Seeds `mcp_bridge/erp_mock.db` (SQLite) with the corresponding ERP purchase-order rows

> ⚠️ **Why this must run before `docker compose up`:** the `ai-worker` service mounts `mcp_bridge/erp_mock.db` as a bind mount. If the file doesn't exist on the host first, Docker creates it as a directory and the worker fails to open the SQLite database. **Always seed before you start the stack.**

---

### Step 4 — Start the backend

```bash
make up-build
```

Or manually:

```bash
docker compose up --build -d
```

This brings up the full backend stack:

| Service | Description | Port |
|---|---|---|
| `postgres` | PostgreSQL 16 (Temporal + `invoice_app` + `langfuse` databases) | `5432` |
| `temporal` | Temporal server | `7233` (gRPC) |
| `temporal-ui` | Temporal Web UI | `8085` |
| `temporal-admin-setup` | One-shot: registers the `default` namespace | — |
| `api-gateway` | FastAPI HTTP layer | `8000` |
| `ai-worker` | Temporal worker (DSPy + LangGraph + MCP) | — |
| `langfuse` | LLM observability UI (self-hosted) | `3030` |
| `langfuse-worker` | Langfuse async event ingestion worker | — |
| `clickhouse` | OLAP store for Langfuse traces/observations | — |
| `redis` | Queue / cache for Langfuse | — |
| `minio` | S3-compatible object store for Langfuse events/media | `9090` (API) / `9091` (console) |
| `minio-setup` | One-shot: creates the `langfuse` bucket in MinIO | — |

Wait ~20 seconds for Temporal and Langfuse to finish provisioning, then verify health:

```bash
make ps
curl http://localhost:8000/health
```

---

### Step 5 — Start the frontend

In a separate terminal:

```bash
make frontend
```

Or manually:

```bash
cd frontend
npm install                  # Install Node dependencies (first time only)
npx prisma db push           # Create the `app` schema + tables in Postgres
npx prisma generate          # Generate the type-safe Prisma client
npm run dev
```

> 🎯 Prisma's `db push` is idempotent — safe to re-run after schema edits.

---

### Step 6 — Open the dashboard

You're live! 🎉

| URL | What's there |
|---|---|
| 🖥️ **[http://localhost:3000](http://localhost:3000)** | Next.js dashboard — upload invoices, trigger reconciliation, view persisted history |
| 📋 **[http://localhost:8000/docs](http://localhost:8000/docs)** | FastAPI OpenAPI / Swagger UI |
| ⏱️ **[http://localhost:8085](http://localhost:8085)** | Temporal Web UI — inspect workflow runs, retries, and replays |
| 🔍 **[http://localhost:3030](http://localhost:3030)** | Langfuse — LLM observability, traces, cost tracking |

---

### Langfuse self-hosted setup

Langfuse runs as a Docker service on port **3030** (to avoid conflicting with Next.js on port 3000). It shares the existing Postgres container but uses a separate `langfuse` database, which `make up` / `make up-build` create idempotently via the `langfuse-db-create` target (see `Makefile`).

**After Langfuse starts:**

1. Open **http://localhost:3030** and create an admin account. Sign-up is disabled after the first account (`AUTH_DISABLE_SIGNUP=true` in `docker-compose.yml`) — to add more users, temporarily flip it off.
2. Create a new project and generate API keys
3. Update `.env` with the new `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`
4. Restart the backend: `docker compose restart api-gateway ai-worker`

Generate the container-side Langfuse secrets once (they must stay stable — rotating them invalidates existing sessions and encrypted data):

```bash
# Write each into .env
openssl rand -hex 32  # → LANGFUSE_NEXTAUTH_SECRET
openssl rand -hex 32  # → LANGFUSE_SALT
openssl rand -hex 32  # → LANGFUSE_ENCRYPTION_KEY (must be 64 hex chars)
```

---

## 🧪 End-to-end test

1. Open the dashboard at `http://localhost:3000`
2. Click **Select PDFs** → upload one or more files from `mock_data/invoices/`
3. Click **Upload Selected Invoices**
4. Click **Scan & Process Directory** to trigger a Temporal batch workflow
5. Watch the live status badge change from `RUNNING` → `COMPLETED`
6. The dashboard auto-saves the result via a Server Action; refresh the page to see it persist in the **Recent Batch Results** history
7. Inspect workflow internals at the Temporal UI (`localhost:8085`) — every activity, retry, and parameter is replayable

---

## 📁 Project structure

```
.
├── api_gateway/            # FastAPI HTTP layer (upload, batch trigger, status)
├── ai_worker/              # Temporal worker
│   ├── workflows.py        # Deterministic batch reconciliation workflow
│   ├── activities.py       # Side-effecting activities (PDF parse, LLM, routing)
│   ├── dspy_engine.py      # DSPy module — structured invoice extraction
│   ├── agent_graph.py      # LangGraph agent — ERP reconciliation + span redaction
│   ├── llm_router.py       # Thread-safe LM singleton (primary + fast fallback chain)
│   └── worker.py           # Temporal worker entrypoint + OpenInference instrumentation
├── mcp_bridge/             # Zero-trust ERP integration
│   ├── server.py           # FastMCP server exposing ERP lookups as tools
│   ├── init_db.py          # Bootstraps the SQLite schema
│   └── erp_mock.db         # Seeded by seed_data.py (do NOT commit changes)
├── shared/
│   └── schemas.py          # Pydantic v2 contracts (InvoiceData, ReconciliationDecision)
├── frontend/               # Next.js dashboard
│   ├── src/app/
│   │   ├── page.tsx        # Main dashboard (Editorial Enterprise design system)
│   │   ├── layout.tsx      # Sidebar + brand chrome
│   │   └── actions.ts      # Server Actions (saveBatchResult, getRecentBatches, getDashboardStats)
│   ├── src/lib/prisma.ts   # PrismaClient singleton with PrismaPg adapter
│   ├── prisma/schema.prisma# Batch + Invoice models
│   └── prisma.config.ts    # Prisma 7 CLI configuration
├── mock_data/              # Sample invoices + processed buckets (approved/, discrepancy/)
├── docker-compose.yml      # Full backend stack
├── seed_data.py            # ⚠️ Run first to bootstrap mock data
└── pyproject.toml          # Python deps managed by uv
```

---

## 🛠️ Makefile targets

The `Makefile` provides shortcuts for common workflows:

| Command | Description |
|---|---|
| `make bootstrap` | **First run from fresh clone** — install + seed + up-build + frontend |
| `make dev` | Daily use — Docker stack (rebuild) + Next.js dev server |
| `make install` | Install all dependencies (`uv sync` + `npm ci`) |
| `make seed` | Regenerate mock PDFs + `erp_mock.db` |
| `make up` | Start Docker stack without rebuild |
| `make up-build` | Start Docker stack with rebuild |
| `make down` | Stop all containers (volumes preserved) |
| `make frontend` | Run Next.js dev server only (assumes Docker stack is running) |
| `make logs` | Follow Docker Compose logs |
| `make ps` | List running containers |
| `make db-push` | Generate Prisma client + sync schema to Postgres |

---

## 🔧 Common commands (without Makefile)

```bash
# Backend
docker compose up --build -d        # Bring up all services
docker compose logs -f ai-worker    # Tail the AI worker
docker compose down                 # Stop everything (volumes preserved)

# Python (local)
uv sync                             # Install / update dependencies
uv run python seed_data.py          # Re-seed mock data
uv run pytest                       # Run tests

# Frontend
cd frontend
npm run dev                         # Next.js dev server
npm run lint                        # ESLint
npx prisma studio                   # Visual DB browser at localhost:5555
npx prisma db push                  # Sync schema to Postgres
npx prisma generate                 # Generate Prisma client types
```

---

## 📐 Architectural rules (for contributors)

1. **Microservices only** — never combine `api_gateway`, `mcp_bridge`, and `ai_worker` into a single process.
2. **Durable execution** — all business logic lives in Temporal workflows + activities. Workflows are 100% deterministic (no `datetime.now()`, no raw HTTP).
3. **No prompt engineering** — extraction uses DSPy, not LangChain or raw prompt strings.
4. **Strict typing** — Pydantic v2 with `ConfigDict(strict=True)` on Python; `strict: true` on TypeScript.
5. **Zero trust** — database access from the agent goes through the MCP bridge, never directly.

See [`CLAUDE.md`](./CLAUDE.md) for the full contributor guide.

---

## 📜 License

MIT — built as a portfolio piece demonstrating production-grade AI engineering patterns.
