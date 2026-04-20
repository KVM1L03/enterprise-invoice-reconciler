# Enterprise Invoice Reconciler — local orchestration
# Requires: Docker, uv, Node 20+ (see frontend/package.json)

ROOT := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))

.PHONY: help install seed up up-build down dev frontend logs ps db-push postgres-wait langfuse-db-create

.DEFAULT_GOAL := help

help:
	@echo "Enterprise Invoice Reconciler"
	@echo ""
	@echo "  make dev        — full Docker stack (rebuild) then Next.js dev server"
	@echo "  make install    — uv sync + npm ci (frontend)"
	@echo "  make seed       — regenerate mock PDFs + erp_mock.db"
	@echo "  make up         — Postgres + ensure DB langfuse, then docker compose up -d"
	@echo "  make up-build   — same as up with --build (images + Langfuse v3 stack)"
	@echo "  make down       — docker compose down"
	@echo "  make frontend   — only Next.js (expects stack already running)"
	@echo "  make logs       — follow docker compose logs"
	@echo "  make ps         — docker compose ps"
	@echo "  make db-push    — prisma generate + db push (frontend; needs DATABASE_URL)"
	@echo ""
	@echo "Docker stack includes: Temporal, API gateway, AI worker, Langfuse v3 (web + worker),"
	@echo "  ClickHouse, Redis, MinIO (S3-compatible), shared Postgres."
	@echo ""
	@echo "  Langfuse UI     http://localhost:3030"
	@echo "  MinIO API       http://localhost:9090   (console :9091, user minio / see LANGFUSE_MINIO_ROOT_PASSWORD)"
	@echo "  Temporal UI     http://localhost:8085"
	@echo "  API docs        http://localhost:8000/docs"
	@echo ""
	@echo "Frontend: frontend/.env.local — DATABASE_URL for Prisma dashboard."
	@echo "Backend:  root .env — LLM keys + LANGFUSE_* (PUBLIC_KEY/SECRET_KEY from Langfuse project,"
	@echo "          LANGFUSE_NEXTAUTH_SECRET, LANGFUSE_SALT, LANGFUSE_ENCRYPTION_KEY, optional"
	@echo "          LANGFUSE_REDIS_AUTH, LANGFUSE_MINIO_ROOT_PASSWORD, LANGFUSE_CLICKHOUSE_*)."

install:
	cd "$(ROOT)" && uv sync
	cd "$(ROOT)/frontend" && npm ci

seed:
	cd "$(ROOT)" && uv run python seed_data.py

# Wait until Postgres accepts connections (max ~60s).
postgres-wait:
	@echo "[make] Waiting for Postgres..."
	@cd "$(ROOT)" && i=0; until docker compose exec -T postgres pg_isready -U temporal >/dev/null 2>&1; do \
		i=$$((i+1)); test $$i -gt 60 && { echo "[make] Postgres not ready"; exit 1; }; \
		sleep 1; \
	done; echo "[make] Postgres is ready"

# Idempotent: CREATE DATABASE langfuse for Langfuse v3 metadata (must exist before web/worker migrate).
langfuse-db-create:
	@echo "[make] Ensuring database langfuse exists..."
	@cd "$(ROOT)" && \
		(docker compose exec -T postgres psql -U temporal -tAc "SELECT 1 FROM pg_database WHERE datname = 'langfuse'" | grep -q 1) || \
		docker compose exec -T postgres psql -U temporal -c "CREATE DATABASE langfuse OWNER temporal;"

# Start Postgres first so we can create langfuse DB before Langfuse containers run migrations.
up:
	cd "$(ROOT)" && docker compose up -d postgres
	@$(MAKE) postgres-wait langfuse-db-create
	cd "$(ROOT)" && docker compose up -d

up-build:
	cd "$(ROOT)" && docker compose up -d postgres
	@$(MAKE) postgres-wait langfuse-db-create
	cd "$(ROOT)" && docker compose up -d --build

down:
	cd "$(ROOT)" && docker compose down

logs:
	cd "$(ROOT)" && docker compose logs -f

ps:
	cd "$(ROOT)" && docker compose ps

# Full stack in one terminal: infra in background, UI in foreground
dev: up-build
	cd "$(ROOT)/frontend" && npm run dev

frontend:
	cd "$(ROOT)/frontend" && npm run dev

db-push:
	cd "$(ROOT)/frontend" && npx prisma generate && npx prisma db push
