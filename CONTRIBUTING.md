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

## Backend

```bash
cd backend && uv pip install -e ".[dev]" && alembic upgrade head && pytest
```

## Frontend

```bash
cd frontend && npm ci && npm run lint && npm run build
```

## Migrations

Toujours créer une révision Alembic dédiée ; ne pas éditer une migration déjà appliquée sur une base partagée.
