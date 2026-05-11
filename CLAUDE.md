# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Enterprise Invoice Reconciler — an AI-powered system that extracts data from invoices, reconciles them against an ERP database, and routes decisions (APPROVED / DISCREPANCY / HUMAN_REVIEW_NEEDED). Early-stage scaffold; most module files are stubs.

## Commands

```bash
# Install dependencies (uses uv)
uv sync

# Run the placeholder entrypoint
uv run python main.py

# Run the API gateway (FastAPI)
uv run uvicorn api_gateway.main:app --reload

# Run the MCP bridge server
uv run python -m mcp_bridge.server

# Seed / reset the mock ERP database
uv run python -m mcp_bridge.init_db

# Run tests
uv run pytest tests/
uv run pytest --cov=. --cov-report=term-missing   # with coverage

# Lint (Python)
uv run ruff check .

# Promptfoo eval suite (zero API cost by default via mock provider)
npx promptfoo eval
npx promptfoo view                # open results in browser

# LLM-as-judge evals (set EVAL_DRY_RUN=1 for deterministic/free run)
EVAL_DRY_RUN=1 uv run python evals/llm_judge_evals.py

# Frontend
cd frontend && npm ci && npm run lint
cd frontend && npm run dev        # dev server on http://localhost:3000
```

## Architecture

The system has four packages that communicate at runtime:

- **api_gateway/** — FastAPI HTTP layer. Receives invoice submissions and returns reconciliation results.
- **ai_worker/** — Temporal-based worker that orchestrates the AI pipeline:
  - `workflows.py` / `activities.py` — Temporal workflow and activity definitions for durable execution.
  - `dspy_engine.py` — DSPy module for structured LLM extraction of invoice fields.
  - `agent_graph.py` — LangGraph agent that checks extracted data against the ERP and makes the reconciliation decision.
- **mcp_bridge/** — FastMCP server exposing ERP database lookups as MCP tools (so the LangGraph agent can call them).
  - `init_db.py` — Seeds/initializes the mock ERP database.
- **shared/** — Pydantic models shared across packages (`InvoiceData`, `ReconciliationDecision`).

### Data flow

```
Invoice → api_gateway → Temporal workflow (ai_worker)
  → DSPy extraction (dspy_engine) → InvoiceData
  → LangGraph agent (agent_graph) calls MCP tools (mcp_bridge) to query ERP
  → ReconciliationDecision → api_gateway response
```

### Key dependencies

- **Temporal** for workflow orchestration and durability
- **DSPy** for structured LLM output (invoice field extraction)
- **LangGraph** for the reconciliation agent graph
- **FastMCP** for exposing ERP lookups as MCP tool calls
- **Langfuse** for LLM observability (cost, prompt tracking, evals)
- **Promptfoo** + **LLM-as-judge** for offline eval suite (`evals/`)
- **Next.js 15** (App Router) frontend in `frontend/`
- Python >=3.12, managed with **uv**

## Architecture Rules

1. **Microservices Only**: This is a distributed system. Never combine `api_gateway`, `mcp_bridge`, and `ai_worker` into a single file.
2. **Durable Execution**: All business logic must be written as Temporal Workflows (`workflows.py`) and Activities (`activities.py`). Workflows MUST be 100% deterministic (no HTTP calls, no raw `datetime.now()`).
3. **No Prompt Engineering**: We use DSPy (`dspy-ai`) for extraction. Do NOT use LangChain or raw prompt templates.
4. **Strict Typing**: Use Pydantic v2 with `model_config = ConfigDict(strict=True)` for all data contracts.
5. **Zero Trust**: Database connections happen ONLY via the `fastmcp` bridge.

## Conventions

- Shared data models live in `shared/schemas.py` and are imported by other packages — keep them as the single source of truth.
- `mock_data/invoices/` holds sample invoice files for development/testing.
- Frontend shared utilities live in `frontend/src/lib/`. The `formatUsd()` function in `format.ts` uses adaptive precision (2/4/6 decimal places) so sub-dollar LLM costs like `$0.0034` never silently round to `$0.00`.
- The `.gitignore` has a `!frontend/src/lib/` negative pattern to prevent the Python `lib/` venv rule from swallowing frontend source files. Do not remove this.
- Eval fixtures live in `evals/fixtures/` (plain-text invoices used by the mock Promptfoo provider).

## CI / Testing

Three parallel GitHub Actions jobs (`.github/workflows/ci.yml`):

| Job | Tool | Cache key |
|-----|------|-----------|
| `python-lint` | `ruff check .` | `uv.lock` via `astral-sh/setup-uv@v5` |
| `python-test` | `pytest --cov` + Codecov upload | `uv.lock` |
| `frontend-lint` | `eslint` | `frontend/package-lock.json` via `actions/setup-node@v4 cache:'npm'` |

The `conftest.py` session fixture calls `init_db()` before any test runs, so `erp_mock.db` is always present in CI (it is gitignored and must not be committed).

## Eval Suite

Two complementary eval layers:

1. **Promptfoo** (`promptfooconfig.yaml` + `evals/mock_dspy_provider.py`) — zero API cost. The mock provider regex-matches the invoice ID from the prompt and returns pre-baked fixture JSON. Run: `npx promptfoo eval`.
2. **LLM-as-judge** (`evals/llm_judge_evals.py`) — uses `litellm.acompletion` with a real judge model (`JUDGE_MODEL`, default `claude-haiku-4-5-20251001`). Set `EVAL_DRY_RUN=1` for a deterministic, free dry-run that applies business rules locally without calling any LLM.

## Known Gotchas

- **Langfuse cost shows $0**: The `vertex_ai/gemini-2.5-flash` model name does not match Langfuse's default pricing table. Fix in Langfuse UI: Settings → Models → Add custom model with regex `^(vertex_ai/)?gemini-2\.5-flash$`, input price `0.0000003`, output price `0.0000025`.
- **`erp_mock.db` missing**: Run `uv run python -m mcp_bridge.init_db` to seed it. Never commit the `.db` file.
- **Temporal workflow stuck**: If activities stop processing, a soft restart (`docker compose down && docker compose up --build`) resolves it without data loss.

## Anti-Patterns & Concurrency Rules

1. **NEVER use global state mutation in asynchronous code** (e.g., inside `asyncio.gather`, Temporal Activities running concurrently). Global state causes race conditions when Temporal workflows run activities in parallel.
2. **NEVER use `dspy.configure()` or `dspy.settings.configure()`**. Always inject the LM locally using `with dspy.context(lm=...):` to ensure thread-safety and avoid `RuntimeError` during parallel execution.
3. **LM instances must be process-wide singletons** created once (thread-safe via `threading.Lock`) and shared across concurrent calls. Each call scopes its usage with `dspy.context(lm=lm)`.

## The "Draft -> Review -> Commit" Execution Pattern
When asked to write or modify critical business logic (Temporal Workflows, FastAPI routes, MCP Tools), you MUST follow this exact sequence:
1. **DRAFT (Internal):** Generate the proposed code in your scratchpad/context. Do NOT write it to the filesystem yet.
2. **REVIEW (Tool Call):** Automatically run the checklist from `.claude/skills/code-review/SKILL.md` against your internal draft.
3. **REFINE (Internal):** If the review highlights async I/O blocks, lack of strict Pydantic models, or Temporal non-determinism, fix the draft.
4. **COMMIT (Disk):** Only after passing the review natively, write the final, production-ready Python code to the actual file.
