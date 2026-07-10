# Set the user and group IDs in docker compose to the same as the host user so new files belong to the host user
# instead of root.
# This can be changed to your own user/group ID here, though these defaults should be fine for most people.
export MY_UID := 1000
export MY_GID := 1000

sync: ## pnpm install and uv sync
	cd apps/backend && uv sync
	pnpm install

build: ## Build backend and frontend Docker images
	@echo "Building backend Docker image..."
	docker build -f apps/backend/Dockerfile --tag backend:latest apps/backend

lint: ## Run linters
	@cd apps/backend && uv run python -c "from app import *" || (echo '🚨 import failed, this means you introduced unprotected imports! 🚨'; exit 1)
	@cd apps/backend && uv run ruff check . --fix --exclude tests --exclude .venv --exclude app/alembic
	@cd apps/backend && uv run ty check . --exclude 'tests/**' --exclude '.venv/**' --exclude 'app/alembic/**'
	@cd apps/backend && uv run black . --exclude '/(tests|\.venv|app/alembic)/'
	@cd apps/backend && uv run isort . --skip tests --skip .venv --skip app/alembic

openapi:  ## Generate OpenAPI schema from FastAPI app
	cd apps/backend && uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > ./openapi.json
	pnpm turbo run generate-client --filter=@edenscale/api

db-init: ## Create all database tables from SQLAlchemy models (dev only — use migrations in prod)
	cd apps/backend && uv run python -c "from app import models; from app.core.database import init_db; init_db(); print('✓ tables created')"

db-seed: ## Seed the database with a demo dataset (idempotent)
	cd apps/backend && uv run python -m scripts.seed_demo

migration: ## Create a new migration
	cd apps/backend && read -p "Enter migration name: " name && uv run alembic revision -m "$$name" --autogenerate

upgrade: ## Apply migrations
	cd apps/backend && uv run alembic upgrade head

downgrade: ## Apply downgrade migrations
	cd apps/backend && uv run alembic downgrade -1

start-manager: ## Start the development manager frontend
	pnpm turbo run dev --filter=manager

start-investor: ## Start the development investor frontend
	pnpm turbo run dev --filter=investor

start-superadmin: ## Start the development superadmin frontend
	pnpm turbo run dev --filter=superadmin

start-backend: ## Start the development backend
	#docker run --name postgres-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=taven -p 5432:5432 -v postgres-data:/var/lib/postgresql postgres
	cd apps/backend && uv run fastapi dev app/main.py --port 8000 --host localhost

start-worker: ## Start arq worker
	cd apps/backend && uv run arq app.worker.WorkerSettings

start-web: ## Start arq worker
	pnpm turbo run dev --filter=web

test:
	cd apps/backend && uv run pytest -v 2>&1

kamal-check: ## Verify op + kamal are installed and signed in (used by build/deploy)
	@command -v op >/dev/null 2>&1 || { echo "🚨 1Password CLI (op) not found — https://developer.1password.com/docs/cli/"; exit 1; }
	@command -v kamal >/dev/null 2>&1 || { echo "🚨 Kamal not found — run 'gem install kamal'"; exit 1; }
	@op whoami >/dev/null 2>&1 || { echo "🚨 Not signed in to 1Password — run 'op signin' (or export OP_SERVICE_ACCOUNT_TOKEN)"; exit 1; }

kamal-build: kamal-check ## Build backend image with Kamal and push to ghcr (secrets via 1Password/op)
	kamal build deliver

kamal-deploy: kamal-check ## Deploy backend with Kamal — pulls fixed :latest image, no build (secrets via 1Password/op)
	kamal deploy --skip-push --version=latest
	kamal app exec --reuse --version=latest "/app/.venv/bin/alembic upgrade head"

kamal-logs: kamal-check ## Tail logs
	kamal app logs -f

.PHONY: help
.DEFAULT_GOAL := help

help:
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

# catch-all for any undefined targets - this prevents error messages
# when running things like make npm-install <package>
%:
	@:
