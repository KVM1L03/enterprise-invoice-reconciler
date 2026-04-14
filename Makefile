# Enterprise Invoice Reconciler — local orchestration
# Requires: Docker, uv, Node 20+ (see frontend/package.json)

ROOT := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))

.PHONY: help install seed up up-build down dev frontend logs ps db-push

.DEFAULT_GOAL := help

help:
	@echo "Enterprise Invoice Reconciler"
	@echo ""
	@echo "  make dev        — Docker stack (Temporal + API + worker) then Next.js dev server"
	@echo "  make install    — uv sync + npm ci (frontend)"
	@echo "  make seed       — regenerate mock PDFs + erp_mock.db"
	@echo "  make up         — docker compose up -d (no rebuild)"
	@echo "  make up-build   — docker compose up -d --build"
	@echo "  make down       — docker compose down"
	@echo "  make frontend   — only Next.js (expects stack already running)"
	@echo "  make logs       — follow docker compose logs"
	@echo "  make ps         — docker compose ps"
	@echo "  make db-push    — prisma generate + db push (frontend; needs DATABASE_URL)"
	@echo ""
	@echo "Frontend: set frontend/.env.local with DATABASE_URL for the dashboard DB."
	@echo "Backend:  root .env for LLM keys (used by api-gateway + ai-worker containers)."

install:
	cd "$(ROOT)" && uv sync
	cd "$(ROOT)/frontend" && npm ci

seed:
	cd "$(ROOT)" && uv run python seed_data.py

up:
	cd "$(ROOT)" && docker compose up -d

up-build:
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
