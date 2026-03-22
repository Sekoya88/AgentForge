.PHONY: db-up dev-ready backend-install backend-migrate backend-dev frontend-dev hooks precommit

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
	cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	cd frontend && npm run dev

# pip install pre-commit && (cd frontend && npm ci) before first run
hooks:
	pre-commit install
	pre-commit install --hook-type commit-msg

precommit:
	pre-commit run --all-files
