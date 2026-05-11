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
| `ai-worker`   | `/` | (override start command — see below) | Dockerfile |
| `frontend`    | `/frontend` | `frontend/railway.toml` | Nixpacks |

The `ai-worker` service reuses the root `Dockerfile` but needs a different
start command. In the dashboard:

> Service Settings → Deploy → Custom Start Command:
> ```
> uv run python -m ai_worker.worker
> ```

No healthcheck path for the worker — Railway treats long-running processes
that don't bind a port as healthy by default.

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

### `api-gateway`

| Variable | Required | Value |
|---|---|---|
| `DATA_DIR` | required | `/app/data` |
| `TEMPORAL_ADDRESS` | required | `<your-ns>.<account>.tmprl.cloud:7233` |
| `TEMPORAL_NAMESPACE` | required | from Temporal Cloud |
| `TEMPORAL_TLS_CERT` / `TEMPORAL_TLS_KEY` | required | TLS material for Temporal Cloud (see Temporal docs) |
| `LANGFUSE_HOST` | required | `https://cloud.langfuse.com` |
| `LANGFUSE_PUBLIC_KEY` | required | from Langfuse project |
| `LANGFUSE_SECRET_KEY` | required | from Langfuse project |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | recommended | `https://cloud.langfuse.com/api/public/otel/v1/traces` |
| `DEMO_MODE` | recommended | `true` (recruiter site) or `false` (private/staging) |
| `DEMO_COOKIE_SECURE` | recommended | `true` (Railway terminates TLS, cookies must be Secure in prod) |
| `PII_SCRUB_TELEMETRY` | recommended | `true` (default — leave unless debugging) |
| LLM provider keys | required | `GOOGLE_APPLICATION_CREDENTIALS` (Vertex) **or** `OPENAI_API_KEY` (legacy). See `ai_worker/llm_router.py`. |

### `ai-worker`

Same as `api-gateway` plus:

| Variable | Required | Value |
|---|---|---|
| `DATA_DIR` | required | `/app/data` (same volume mount) |

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

Then in the **frontend** service's "Deploy" tab, add a pre-deploy command:

```
npx prisma db push
```

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

If the batch hangs in `RUNNING`: the worker isn't reaching Temporal. Check
`TEMPORAL_ADDRESS` + TLS env vars on the `ai-worker` service.

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
