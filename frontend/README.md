# AgentForge — Frontend

Application **Next.js** (App Router), **React**, **Tailwind**. Elle consomme l’API via `NEXT_PUBLIC_API_URL` (JWT dans `localStorage` : `access_token` / `refresh_token`).

## Prérequis

- Node **20+** (aligné CI)
- API backend joignable (même origine CORS configurée côté `CORS_ORIGINS` / regex dans `.env` racine)

## Installation & dev

```bash
npm ci
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Build production locale (proche de ce que tu déploies) :

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run build
npm run start
```

## Scripts

| Commande | Usage |
|----------|--------|
| `npm run dev` | Dev server (hot reload) |
| `npm run build` | Build Next |
| `npm run start` | Serveur après `build` |
| `npm run lint` | ESLint |
| `npm run dev:clean` | Nettoie `.next` puis dev (voir README racine si `ChunkLoadError`) |

## Routes utiles (`src/app/`)

| Chemin | Rôle |
|--------|------|
| `/`, `/login`, `/register` | Landing, auth |
| `/agents`, `/agents/new`, `/agents/[id]` | Liste, création, détail + exécution + skills attachés + historique campagnes |
| `/agents/[id]/builder` | Builder React Flow |
| `/skills`, `/skills/new` | Registry skills |
| `/knowledge` | **RAG** : indexer du texte, sources, tool `retrieve` côté graphe |
| `/campaigns`, `/campaigns/[id]` | Campagnes red-team |
| `/sandbox` | Exécution Python isolée (UX playground) |
| `/finetune` | Jobs fine-tune (**stub** côté backend — voir bannière Labs) |

Layout global : `AppHeader` (nav + état connecté **Sign out**), pages outil sous `ToolShell` (sidebar).

## Client API

- `src/lib/api.ts` — `fetch` JSON + `Authorization`, `setTokens` / `clearTokens`
- `src/lib/sse.ts` — SSE pour exécutions async

## Tests E2E (Playwright)

```bash
npx playwright install chromium
# API + next start — voir ../CONTRIBUTING.md
E2E_EMAIL=... E2E_PASSWORD=... npx playwright test
```

Spec **golden path** : `e2e/golden-path.spec.ts` (skill → agent tool → exécution sync).

## Liens

- README monorepo : `../README.md`
- Parcours manuels pertinents : `../explain.md`
- `../CONTRIBUTING.md`
