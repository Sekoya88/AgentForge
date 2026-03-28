# Docker Compose Production Configuration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a `docker-compose.prod.yml` production-ready configuration with: health checks on all services, restart policies, environment variable isolation via `.env.prod.example`, and a multi-worker uvicorn backend. The current `docker-compose.yml` is dev-only (hot reload, no restart, no health checks).

**Architecture:** Separate `docker-compose.prod.yml` that uses pre-built images or builds with production targets. Services: `db` (postgres+pgvector), `redis`, `backend` (4 uvicorn workers), `frontend` (next start). All services have health checks and `restart: unless-stopped`. Secrets via environment variables (not baked into image). Backend uses `CMD` with `gunicorn` or `uvicorn --workers 4`.

**Tech Stack:** Docker Compose v2, PostgreSQL 16+pgvector, Redis 7, uvicorn, Next.js `next start`.

---

### Task 1: Create .env.prod.example

**Files:**
- Create: `.env.prod.example`

- [ ] **Step 1: Create the file**

```bash
# .env.prod.example — copy to .env.prod and fill in values
# Never commit .env.prod to git

# === Database ===
POSTGRES_USER=forge
POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD
POSTGRES_DB=agentforge
DATABASE_URL=postgresql+asyncpg://forge:CHANGE_ME_STRONG_PASSWORD@db:5432/agentforge

# === Redis ===
REDIS_URL=redis://redis:6379/0

# === Auth (generate with: python -c "import secrets; print(secrets.token_hex(32))")
JWT_SECRET_KEY=CHANGE_ME_64_CHAR_HEX_SECRET

# === CORS (set to your production domain)
CORS_ORIGINS=https://your-domain.com
CORS_ORIGIN_REGEX=

# === LLM API keys (optional — users can set their own via /settings)
OPENAI_API_KEY=
GOOGLE_API_KEY=

# === Observability (optional)
SENTRY_DSN=
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_ENVIRONMENT=production
LANGFUSE_SECRET_KEY=
LANGFUSE_PUBLIC_KEY=

# === Modal (fine-tuning)
MODAL_ENABLED=false
MODAL_INFERENCE_URL=

# === Frontend
NEXT_PUBLIC_API_URL=https://your-domain.com
NEXT_PUBLIC_SENTRY_DSN=
NEXT_PUBLIC_SENTRY_ENVIRONMENT=production
```

- [ ] **Step 2: Verify .env.prod is in .gitignore**

```bash
grep "env.prod" .gitignore
```

If not found, add it:

```bash
echo ".env.prod" >> .gitignore
```

- [ ] **Step 3: Commit**

```bash
git add .env.prod.example .gitignore
git commit -m "chore(ops): add .env.prod.example for production deployment"
```

---

### Task 2: Create docker-compose.prod.yml

**Files:**
- Create: `docker-compose.prod.yml`

- [ ] **Step 1: Read the current docker-compose.yml to understand the network/volume names**

```bash
cat docker-compose.yml
```

Note the volume names (`pgdata`, etc.) and network configuration.

- [ ] **Step 2: Create docker-compose.prod.yml**

```yaml
# docker-compose.prod.yml — production deployment
# Usage: docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

services:
  db:
    image: pgvector/pgvector:pg16
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "${POSTGRES_USER}", "-d", "${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - agentforge

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    networks:
      - agentforge

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file:
      - .env.prod
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: >
      sh -c "python -m alembic upgrade head &&
             uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --no-access-log"
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8000/health"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - agentforge

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL}
        NEXT_PUBLIC_SENTRY_DSN: ${NEXT_PUBLIC_SENTRY_DSN:-}
        NEXT_PUBLIC_SENTRY_ENVIRONMENT: ${NEXT_PUBLIC_SENTRY_ENVIRONMENT:-production}
    restart: unless-stopped
    depends_on:
      backend:
        condition: service_healthy
    ports:
      - "3000:3000"
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:3000/"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 60s
    networks:
      - agentforge

volumes:
  pgdata:
  redisdata:

networks:
  agentforge:
    driver: bridge
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "feat(ops): add docker-compose.prod.yml with health checks and restart policies"
```

---

### Task 3: Create Dockerfiles

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`

- [ ] **Step 1: Check if Dockerfiles already exist**

```bash
ls backend/Dockerfile frontend/Dockerfile 2>/dev/null || echo "missing"
```

If both exist, skip to Step 4.

- [ ] **Step 2: Create backend/Dockerfile**

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency install
RUN pip install --no-cache-dir uv

COPY pyproject.toml .
COPY app/ app/
COPY migrations/ migrations/
COPY alembic.ini .

RUN uv pip install --system -e "."

EXPOSE 8000

# CMD is overridden in docker-compose.prod.yml to run migrations first
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Create frontend/Dockerfile**

```dockerfile
# frontend/Dockerfile
FROM node:20-slim AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_SENTRY_DSN=
ARG NEXT_PUBLIC_SENTRY_ENVIRONMENT=production
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_SENTRY_DSN=$NEXT_PUBLIC_SENTRY_DSN
ENV NEXT_PUBLIC_SENTRY_ENVIRONMENT=$NEXT_PUBLIC_SENTRY_ENVIRONMENT

RUN npm run build

FROM node:20-slim AS runner

WORKDIR /app
COPY --from=builder /app/.next .next/
COPY --from=builder /app/public public/
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/node_modules node_modules/

EXPOSE 3000

CMD ["npx", "next", "start", "-H", "0.0.0.0", "-p", "3000"]
```

- [ ] **Step 4: Test the backend Docker build**

```bash
cd backend && docker build -t agentforge-backend:test .
```

Expected: Build succeeds, image created.

- [ ] **Step 5: Test the frontend Docker build**

```bash
cd frontend && docker build --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 -t agentforge-frontend:test .
```

Expected: Build succeeds.

- [ ] **Step 6: Commit**

```bash
git add backend/Dockerfile frontend/Dockerfile
git commit -m "feat(ops): add production Dockerfiles for backend and frontend"
```

---

### Task 4: Add ops documentation note to README or CLAUDE.md

- [ ] **Step 1: Add production deployment section to CLAUDE.md**

Append to the end of `CLAUDE.md` (or create a `docs/deployment.md`):

```markdown
## Production Deployment

```bash
# 1. Copy and fill production env
cp .env.prod.example .env.prod
# Edit .env.prod with real secrets

# 2. Start all services
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 3. Verify health
curl http://localhost:8000/health
```

Services: db (5432), redis (6379), backend (8000), frontend (3000).
All behind a reverse proxy (nginx/caddy) in real deployments.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(ops): add production deployment guide"
```
