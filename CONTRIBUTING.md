# Contributing

## Messages de commit (Conventional Commits)

Un hook **`commit-msg`** vérifie le format. Forme :

```text
type(scope optionnel): courte description impérative
```

**Types** courants : `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.

Exemples valides :

- `feat: add Redis-backed campaign jobs`
- `fix(frontend): save graph entry_point`
- `chore: update pre-commit hooks`

Breaking change : `feat(api)!: remove legacy execute path` ou paragraphe `BREAKING CHANGE:` dans le corps du message.

## Hooks (obligatoire avant premier push)

```bash
pip install -r requirements-dev.txt   # ou: pip install pre-commit
# variante monorepo : pre-commit est aussi dans backend (uv) :
#   cd backend && uv pip install pre-commit && uv run pre-commit install
#   uv run pre-commit install --hook-type commit-msg
cd frontend && npm ci
pre-commit install
pre-commit install --hook-type commit-msg   # valide les messages de commit
```

À chaque commit, **Ruff** (backend), **ESLint** et **tsc** (frontend) tournent. Pour tout vérifier manuellement :

```bash
make precommit
# ou
pre-commit run --all-files
```

Ignorer temporairement : `SKIP=frontend-tsc,frontend-lint git commit ...`

## Pousser sur GitHub (Sekoya88)

Dépôt canonique : **[github.com/Sekoya88/AgentForge](https://github.com/Sekoya88/AgentForge)**. Branche de travail par défaut : **`dev`**.

### Cloner

```bash
# HTTPS
git clone https://github.com/Sekoya88/AgentForge.git
cd AgentForge
git checkout dev

# SSH (clé SSH configurée sur ton compte GitHub)
git clone git@github.com:Sekoya88/AgentForge.git
cd AgentForge
git checkout dev
```

Vérifie le remote : `git remote -v` doit montrer `origin` → `Sekoya88/AgentForge` (pas un fork tiers, sauf si tu travailles volontairement sur un fork).

### Avant chaque push

1. `make precommit` (ou `pre-commit run --all-files`) si tu as touché du code.
2. Branche locale alignée : `git fetch origin && git pull origin dev` (résous les conflits si besoin).

### Pousser

```bash
git push origin dev
```

Authentification côté GitHub : **Personal Access Token (HTTPS)** ou **clé SSH** — tout se passe sur ta machine avec **ton** compte ; aucun agent ne pousse à ta place.

Si tu as forké le repo ailleurs, ajoute un remote dédié puis pousse vers ce fork, ex. :

```bash
git remote add myfork git@github.com:<ton-user>/<ton-fork>.git
git push myfork dev
```

## Backend

```bash
cd backend && uv pip install -e ".[dev]" && alembic upgrade head && pytest
```

## Frontend

```bash
cd frontend && npm ci && npm run lint && npm run build
```

## E2E (Playwright)

GitHub Actions job **`e2e`** boots Postgres + Redis, migrates, runs **uvicorn** on `:8000`, **next start** on `:3010`, registers a throwaway user, then `npx playwright test` (see `.github/workflows/ci.yml`).

**Local (API-backed tests):**

1. DB + Redis + `alembic upgrade head` + `uvicorn` on `8000` (see repo `CLAUDE.md`).
2. Register a user once (UI or `POST /api/v1/auth/register`).
3. Build with the same API URL the browser will use:

   ```bash
   cd frontend
   export NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
   npm run build
   npx playwright install chromium
   export E2E_EMAIL='you@example.com'
   export E2E_PASSWORD='your-password'
   export PLAYWRIGHT_SKIP_WEBSERVER=1
   export PLAYWRIGHT_BASE_URL=http://127.0.0.1:3010
   npx next start -H 127.0.0.1 -p 3010   # separate terminal
   npx playwright test
   ```

Public-only tests run without `E2E_*` (the authenticated block is skipped).

**Golden path** (`e2e/golden-path.spec.ts`): creates a skill, an agent with a single `tool` node (`tool_name` = skill name), attaches the skill, runs **sync** execute (stream off) and asserts `HELLO` in the result — same requirements as above.

## Backend observability (optional)

Set `SENTRY_DSN` to enable Sentry for the FastAPI app (`SENTRY_TRACES_SAMPLE_RATE`, `SENTRY_ENVIRONMENT` optional). Unset = no SDK init.

## Migrations

Toujours créer une révision Alembic dédiée ; ne pas éditer une migration déjà appliquée sur une base partagée.
