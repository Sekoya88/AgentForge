FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md alembic.ini ./
COPY app ./app
COPY migrations ./migrations
COPY scripts/docker_entrypoint.sh ./scripts/docker_entrypoint.sh
RUN chmod +x ./scripts/docker_entrypoint.sh

RUN uv pip install --system -e ".[dev]"

EXPOSE 8000

# Runs `alembic upgrade head` then uvicorn on each start (idempotent). Very long
# data migrations should run as a separate pre-deploy job so boot stays fast.
CMD ["./scripts/docker_entrypoint.sh"]
