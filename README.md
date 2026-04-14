# OmniAccountant

## 🔴 Demo

![Nagranieekranuz2026-04-1416-59-13-ezgif com-video-to-gif-converter](https://github.com/user-attachments/assets/67d75802-5075-44da-8b15-6ec949c8c73d)

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
| **AI Engine** | DSPy · LangGraph · PyMuPDF · Langfuse | Structured LLM extraction (no prompt strings), agentic decision graph, PDF text extraction, full LLM observability |
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

**One command to rule them all:**

```bash
make dev
```

This:
1. Installs all dependencies (`uv sync`, `npm ci`)
2. Seeds mock data (`seed_data.py`)
3. Brings up the full Docker stack (Temporal, Postgres, FastAPI, worker)
4. Starts the Next.js dev server in the foreground

Then open:
- **Dashboard:** http://localhost:3000
- **Temporal UI:** http://localhost:8085
- **API Docs:** http://localhost:8000/docs

---

## 📖 Step-by-step setup (if you prefer manual control)

### Step 1 — Configure environment variables

Create a `.env` file in the **project root** (used by FastAPI and the AI worker via Docker `env_file`):

```bash
# LLM Provider (at least one is required)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...

# LLM Observability (optional but recommended)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com

# Temporal (defaults to host networking)
TEMPORAL_ADDRESS=temporal:7233
```

Create `frontend/.env` for Prisma to reach Postgres (the same container Temporal uses, but isolated in its own SQL schema):

```bash
DATABASE_URL="postgresql://temporal:temporal@localhost:5432/temporal?schema=app"
```

> 💡 The frontend uses a dedicated `app` schema so it doesn't collide with Temporal's internal tables in the `public` schema.

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
| `postgres` | PostgreSQL 16 (Temporal + Prisma `app` schema) | `5432` |
| `temporal` | Temporal server | `7233` (gRPC) |
| `temporal-ui` | Temporal Web UI | `8085` |
| `api-gateway` | FastAPI HTTP layer | `8000` |
| `ai-worker` | Temporal worker (DSPy + LangGraph + MCP) | — |

Wait ~20 seconds for Temporal to finish provisioning, then verify health:

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
│   ├── agent_graph.py      # LangGraph agent — ERP reconciliation decisions
│   └── llm_router.py       # Thread-safe LM singleton + Langfuse instrumentation
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
| `make dev` | **Full stack in one command** — seeds, brings up Docker, starts Next.js (TL;DR) |
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
