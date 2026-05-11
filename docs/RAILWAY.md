# Deploying to Railway

This stack ships three Railway services plus two external dependencies you
must provision separately. Don't try to run it on Railway's free tier in
one box — Temporal alone needs more than the free RAM allowance.

```
                          ┌─────────────────────┐
                          │  Temporal Cloud     │  ← managed; free dev tier
                          │  (or self-host)     │     temporal.io/cloud
                          └──────────▲──────────┘
                                     │ gRPC :7233
                                     │
┌───────────────┐   HTTPS    ┌───────┴────────┐  ─→  ┌──────────────┐
│  frontend     │ ─────────→ │  api-gateway   │       │  ai-worker   │
│  (Next.js)    │            │  (FastAPI)     │       │  (Temporal   │
└───────────────┘            └────────┬───────┘       │   worker)    │
                                      │               └──────┬───────┘
                              volume: /app/data              │
                                      │                      │
                                      └──── shared ─────────┘
                                            (mounted on both)

                          ┌─────────────────────┐
                          │  Langfuse Cloud     │  ← managed; free dev tier
                          └─────────────────────┘     cloud.langfuse.com
```

## 1. Provision external dependencies first

You cannot run the stack without these. Both have free dev tiers.

| Dependency | Why | Where |
|---|---|---|
| **Temporal Cloud** | Workflow durability — the api-gateway calls `client.start_workflow`, the ai-worker polls the task queue. Cannot be skipped. | <https://temporal.io/cloud> → create a namespace |
| **Langfuse Cloud** | LLM observability (cost, prompt traces, evals). Without it, the FinOps dashboard returns zeros. | <https://cloud.langfuse.com> → create a project, copy public + secret key |

Self-hosting either of these on Railway is possible (Temporal needs 4 pods,
Langfuse v3 needs ClickHouse + Redis + MinIO) — out of scope here.

## 2. Create the three Railway services

In the Railway dashboard, **New Project → Empty Project**, then add three
services from this GitHub repo. Railway will detect the per-service config:

| Service | Root directory | Config | Builder |
|---|---|---|---|
| `api-gateway` | `/` | `railway.toml` | Dockerfile |
| `ai-worker`   | `/` | `railway.ai-worker.toml` *(recommended)* or dashboard start | Dockerfile |
| `frontend`    | `/frontend` | `frontend/railway.toml` | Nixpacks |

Root `railway.toml` **omits `startCommand`** on purpose: Railway config-as-code
always overrides the dashboard; one file cannot hold two different commands for
two services on the same repo root.

**api-gateway** → Service Settings → Deploy → **Custom Start Command**:

```bash
sh -c "exec uv run uvicorn api_gateway.main:app --host 0.0.0.0 --port ${PORT}"
```

**api-gateway** → set **Healthcheck** path to `/docs` in the dashboard (not in
shared TOML — it would wrongly apply to every service using that file).

**ai-worker** (pick one):

1. **Recommended:** Settings → *Config as code* → config file path **`/railway.ai-worker.toml`** (worker `startCommand` lives in git).

2. Or leave the default `railway.toml` and set **Custom Start Command** to:

```bash
uv run python -m ai_worker.worker
```

Clear **Pre-deploy Command** on the worker unless you have a real pre-step
(migrations, etc.) — do not run the worker there.

### Self-hosted Temporal on Railway (fourth service)

If you run ``temporalio/auto-setup`` plus a Railway Postgres dedicated to Temporal:

1. Enable **private networking** on **api-gateway**, **ai-worker**, and **temporal**.
   Plain ``TCP timeout`` to ``*.railway.internal:7233`` with working DNS usually
   means the mesh path is blocked or Temporal is not listening on ``7233``.
2. Set ``TEMPORAL_ADDRESS`` via a variable reference such as
   ``${{temporal.RAILWAY_PRIVATE_DOMAIN}}:7233`` (use your Temporal service name).
3. **API gateway** uses Temporal's ``lazy=True`` client: ``/docs`` can succeed before
   the first gRPC handshake; workflow starts open the channel.
   **Worker** retries connect with ``TEMPORAL_CONNECT_RETRIES`` (default ``36``)
   and ``TEMPORAL_CONNECT_RETRY_DELAY`` seconds (default ``5``).

## 3. Attach the persistent volume (api-gateway only)

The api-gateway writes:
- SQLite ERP database: `/app/data/mcp_bridge/erp_mock.db`
- Demo invoice PDFs: `/app/data/mock_data/invoices/<session_id>/`
- Approved / discrepancy archives: `/app/data/mock_data/{approved,discrepancy}/`

Without a volume, every redeploy wipes all demo sessions and the canonical
ERP seed has to re-run on every boot (which is fine — `init_db` is
idempotent — but session PDFs are lost).

> **api-gateway → Settings → Volumes → Add Volume**
> - **Mount path**: `/app/data`
> - **Size**: 1 GB is plenty (PDFs are ~5 KB each, demo session TTL is 2 h)

The `ai-worker` service should mount the **same volume** so it can read
the per-session PDFs the api-gateway wrote and move them into
`approved/` / `discrepancy/`. Railway supports attaching a volume to
multiple services — repeat the above for `ai-worker` and use the same
mount path `/app/data`.

## 4. Environment variables

Set these in **Service Settings → Variables** for each service. Variables
marked **`required`** must be set before the service will boot cleanly;
**`recommended`** keep behaviour sane in production.

Temporal and Langfuse use the **official** Temporal Python SDK and Langfuse
SDK environment variable names. See:

- Temporal: https://docs.temporal.io/references/client-environment-configuration
- Langfuse Python: ``LANGFUSE_BASE_URL`` (preferred) or ``LANGFUSE_HOST``

### `api-gateway`

| Variable | Required | Value |
|---|---|---|
| `DATA_DIR` | required | `/app/data` |
| `TEMPORAL_ADDRESS` | required | Temporal Frontend address, e.g. Cloud `namespace.acct.tmprl.cloud:7233` or internal `hostname:7233` |
| `TEMPORAL_NAMESPACE` | recommended | Omit or `default` for local/docker; **must match your Temporal Cloud namespace** |
| `TEMPORAL_API_KEY` | Temporal Cloud recommended | Namespace API key (TLS is enabled automatically when set). See Temporal Cloud docs |
| mTLS alternative | Cloud optional | ``TEMPORAL_TLS_CLIENT_CERT_PATH`` + ``TEMPORAL_TLS_CLIENT_KEY_PATH`` (or ``*_DATA``). See Temporal env reference |
| `TEMPORAL_CONFIG_FILE` | optional | Path to TOML profiles inside the container; unset = env-only config (recommended for Railway) |
| `TEMPORAL_PROFILE` | optional | Profile name when using TOML; defaults per SDK |
| `FRONTEND_ORIGINS` | required in prod demo | Public URL(s) of the Next.js frontend, comma-separated — required for browser CORS (see `api_gateway/main.py`) |
| `LANGFUSE_BASE_URL` | required if tracing on | `https://cloud.langfuse.com` or self-hosted base URL (`LANGFUSE_HOST` still works, deprecated name) |
| `LANGFUSE_PUBLIC_KEY` | required if tracing on | from Langfuse project |
| `LANGFUSE_SECRET_KEY` | required if tracing on | from Langfuse project |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | recommended | e.g. `https://cloud.langfuse.com/api/public/otel/v1/traces` when exporting OTel spans to Langfuse Cloud |
| `LANGFUSE_TRACING_ENABLED` | optional | `false` to disable Langfuse telemetry (FinOps/charts may stay empty) |
| `OTEL_SDK_DISABLED` | optional | `true` with tracing off |
| `DEMO_MODE` | recommended | `true` (recruiter site) or `false` (private/staging) |
| `DEMO_COOKIE_SECURE` | recommended | `true` (Railway terminates TLS, cookies must be Secure in prod) |
| `PII_SCRUB_TELEMETRY` | recommended | `true` (default — leave unless debugging) |
| LLM provider keys | not on gateway API path | Inference runs in ``ai-worker``; gateway only starts workflows and exposes FinOps |

**Incorrect / unsupported names:** do not use `TEMPORAL_TLS_CERT` / `TEMPORAL_TLS_KEY` — use ``TEMPORAL_TLS_CLIENT_CERT_PATH`` and ``TEMPORAL_TLS_CLIENT_KEY_PATH`` per Temporal docs.

### `ai-worker`

Mirror **Temporal**, **Langfuse/demo**, and **tracing** variables from ``api-gateway`` plus LLM inference:

| Variable | Required | Value |
|---|---|---|
| `DATA_DIR` | required | `/app/data` (same volume mount as gateway) |
| ``LLM_PROVIDER`` | required | ``vertex_ai`` or ``api_keys`` — see ``ai_worker/llm_router.py`` |
| ``GEMINI_API_KEY`` / Vertex / OpenAI… | required | Provider credentials per ``LLM_PROVIDER`` |
| ``TEMPORAL_CONNECT_RETRIES`` | optional | Default ``36`` — worker backoff when Temporal boots slowly |
| ``TEMPORAL_CONNECT_RETRY_DELAY`` | optional | Default ``5`` (seconds between attempts) |

### `frontend`

| Variable | Required | Value |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | required | Public URL of the api-gateway service, e.g. `https://api-gateway-production.up.railway.app` |
| `NEXT_PUBLIC_DEMO_MODE` | recommended | Must match `DEMO_MODE` on the backend |
| `DATABASE_URL` | required | Railway-managed Postgres connection string (see step 5) |
| `DEMO_MODE` | recommended | Same as `NEXT_PUBLIC_DEMO_MODE` — server actions need the un-prefixed name |

> `NEXT_PUBLIC_*` variables are **inlined at build time** by Next.js. Changing
> them requires a fresh deploy — restarting the service is not enough.

## 5. Postgres (Prisma batch history)

The frontend's Prisma client needs Postgres. Add a managed Postgres
plugin in Railway (**+ New → Database → PostgreSQL**) and reference it
from the frontend service:

> frontend → Variables → New → "Add Reference" → `DATABASE_URL` ← Postgres plugin

When using **Railway config-as-code**, ``frontend/railway.toml`` defines
``preDeployCommand`` as a **single-shell string** (Railway rejects argv-style arrays
here). Duplicate the command manually in the dashboard only if deploy omits repo config.

This applies `frontend/prisma/schema.prisma` (including the `Batch.sessionId`
column added for demo isolation) on every deploy. Safe — `db push` is
idempotent and never destructive for additive changes.

## 6. Post-deploy verification

```bash
# Backend boots and seeds the ERP
curl https://<api-gateway-url>/docs        # 200 OK
curl -X POST https://<api-gateway-url>/demo/init   # in DEMO_MODE=true

# Frontend reaches the backend
open https://<frontend-url>                # dashboard renders
# Click "Scan & Process Directory" → batch should reach COMPLETED in <60s
```

If the gateway logs ``tcp connect … TimedOut`` toward Temporal: verify **private
networking**, that every backend service resolves the **same**
``TEMPORAL_ADDRESS``, and Temporal listens on ``7233``. For Temporal Cloud instead,
use the Cloud endpoint plus ``TEMPORAL_NAMESPACE`` / ``TEMPORAL_API_KEY`` (or mTLS).

If the batch hangs in ``RUNNING`` after connect succeeds: check worker logs LLM /
activity errors; Temporal env vars must match on gateway and worker.

If the FinOps page shows $0: Langfuse hasn't ingested traces yet, or the
Vertex model is missing from Langfuse's pricing table — see CLAUDE.md
"Known Gotchas".

## 7. Operating the demo-mode cleanup

The APScheduler in the api-gateway prunes SQLite + filesystem state every
15 minutes (sessions > 2 h old). For the Postgres `Batch` rows, run the
SQL snippet from `scripts/cleanup_demo.sql` as a Railway cron service:

> **+ New → Empty Service**
> Service name: `demo-cleanup-cron`
> Start command: `psql "$DATABASE_URL" -f /scripts/cleanup_demo.sql`
> Schedule: every 15 min (Railway → Settings → Cron Schedule: `*/15 * * * *`)
