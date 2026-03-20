#!/usr/bin/env bash
# Démarre Postgres + Redis (Docker), attend que la DB soit prête, applique Alembic.
# Prérequis : Docker, backend installé avec `uv pip install -e ".[dev]"` (psycopg2 pour Alembic).

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! docker info >/dev/null 2>&1; then
  echo "Docker n’est pas accessible. Démarre Docker Desktop puis relance ce script."
  exit 1
fi

echo "→ docker compose up -d db redis"
docker compose up -d db redis

echo "→ Attente Postgres (forge @ localhost:5433)…"
ok=0
for i in $(seq 1 90); do
  if docker compose exec -T db pg_isready -U forge -d agentforge >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 1
done
if [[ "$ok" -ne 1 ]]; then
  echo "Timeout : Postgres ne répond pas. Vérifie : docker compose ps  &&  docker compose logs db"
  exit 1
fi
echo "→ Postgres prêt."

echo "→ alembic upgrade head (depuis backend/, .env racine lu par migrations/env.py)"
cd "$ROOT/backend"
if ! alembic upgrade head; then
  echo ""
  echo "Si l’erreur parle de psycopg2 / driver :"
  echo "  cd backend && source .venv/bin/activate && uv pip install -e \".[dev]\""
  exit 1
fi

echo ""
echo "✓ Stack locale OK."
echo ""
echo "  Terminal 1 — API :"
echo "    cd $ROOT/backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "  Terminal 2 — UI :"
echo "    cd $ROOT/frontend && npm run dev"
echo ""
echo "  Puis : http://localhost:3000/register  →  /login"
