.PHONY: quick-start db-up dev-ready backend-install backend-migrate backend-dev frontend-dev hooks precommit seed tools test e2e openapi-export openapi-codegen-ts

quick-start: dev-ready
	@if command -v lsof >/dev/null 2>&1 && lsof -ti :8000 >/dev/null 2>&1; then \
	  echo "WARNING: port 8000 is already in use — another process may answer before AgentForge; API calls from the UI may fail."; \
	fi
	@echo "Lancement du backend et du frontend en local..."
	@echo "Backend dispo sur http://localhost:8000"
	@echo "Frontend dispo sur http://localhost:3000"
	@npx concurrently -k -n "backend,frontend" -c "cyan,magenta" "cd backend && uv run uvicorn app.main:app --reload --reload-exclude='modal_functions' --host 0.0.0.0 --port 8000" "cd frontend && npm run dev"

db-up:
	docker compose up -d db redis

# Postgres + Redis + Alembic (attend que la DB soit prête)
dev-ready: db-up
	@echo "Waiting for Postgres..."
	@i=0; \
	while [ $$i -lt 90 ]; do \
	  docker compose exec -T db pg_isready -U forge -d agentforge >/dev/null 2>&1 && break; \
	  i=$$((i+1)); sleep 1; \
	done; \
	docker compose exec -T db pg_isready -U forge -d agentforge >/dev/null 2>&1 || (echo "Postgres timeout"; exit 1)
	cd backend && source .venv/bin/activate && alembic upgrade head

backend-install:
	cd backend && uv pip install -e ".[dev]"

backend-migrate:
	cd backend && source .venv/bin/activate && alembic upgrade head

backend-dev:
	cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --loop asyncio

frontend-dev:
	cd frontend && npm run dev

# pip install pre-commit && (cd frontend && npm ci) before first run
hooks:
	pre-commit install
	pre-commit install --hook-type commit-msg

precommit:
	pre-commit run --all-files

seed:
	cd backend && uv run python ../scripts/seed.py

tools:
	docker compose --profile tools up -d pgadmin

test:
	cd backend && uv run pytest -q

e2e:
	cd frontend && npx playwright test

# Export OpenAPI schema (requires backend deps)
openapi-export:
	cd backend && uv run python ../scripts/export_openapi.py

# Regenerate TypeScript types for @agentforge/sdk (requires npm i in sdk-js)
openapi-codegen-ts: openapi-export
	cd sdk-js && npm run gen:api
