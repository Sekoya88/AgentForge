.PHONY: db-up backend-install backend-migrate backend-dev frontend-dev hooks precommit

db-up:
	docker compose up -d db redis

backend-install:
	cd backend && uv pip install -e ".[dev]"

backend-migrate:
	cd backend && alembic upgrade head

backend-dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	cd frontend && npm run dev

# pip install pre-commit && (cd frontend && npm ci) before first run
hooks:
	pre-commit install
	pre-commit install --hook-type commit-msg

precommit:
	pre-commit run --all-files
