# AgentForge — Frontend

**Next.js** (App Router), **React**, **Tailwind** application. Consumes the API via `NEXT_PUBLIC_API_URL` (JWT in `localStorage`: `access_token` / `refresh_token`).

## Prerequisites

- Node **20+** (aligned with CI)
- Backend API reachable (CORS configured via `CORS_ORIGINS` / regex in root `.env`)

## Install & dev

```bash
npm ci
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Production build:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run build
npm run start
```

## Scripts

| Command | Usage |
|---------|-------|
| `npm run dev` | Dev server (hot reload) |
| `npm run build` | Build Next |
| `npm run start` | Serve after `build` |
| `npm run lint` | ESLint |
| `npm run dev:clean` | Clean `.next` then dev |

## Pages (`src/app/`)

| Path | Role |
|------|------|
| `/` | Landing page (redirects to `/dashboard` if authenticated) |
| `/login`, `/register` | Auth flows |
| `/dashboard` | Aggregate stats, recent executions, quick actions |
| `/agents`, `/agents/new` | Agent list (with import JSON), creation (with templates + AI gen) |
| `/agents/[id]` | Detail: execute, skills, red-team, versions, export JSON, delete |
| `/agents/[id]/builder` | Visual graph builder (React Flow) |
| `/skills`, `/skills/new`, `/skills/[id]` | Skills registry, create, detail/edit/validate/delete |
| `/knowledge` | RAG corpus: file upload (drag & drop), text ingest, sources list |
| `/campaigns`, `/campaigns/[id]` | Red-team campaigns list, structured detail report |
| `/executions` | Paginated execution history across all agents |
| `/sandbox` | Python execution playground |
| `/finetune` | Fine-tune jobs (Labs — backend stub) |
| `/settings` | Read-only system configuration |
| `/profile` | User info, change password |

## Layout

- `AppHeader` — top nav with auth state (Profile / Sign out)
- `ToolShell` — sidebar navigation for all tool pages (Dashboard, Agents, Sandbox, Campaigns, Skills, Knowledge, Executions, Finetune, Settings, Profile)

## Client libraries

- `src/lib/api.ts` — `fetch` JSON + `Authorization`, `setTokens` / `clearTokens`
- `src/lib/sse.ts` — SSE for async executions

## E2E tests (Playwright)

```bash
npx playwright install chromium
# API + next start — see ../CONTRIBUTING.md
E2E_EMAIL=... E2E_PASSWORD=... npx playwright test
```

Specs: `e2e/golden-path.spec.ts` (skill → agent tool → sync execution), `e2e/ui-audit.spec.ts` (auth + page accessibility).

## Links

- Monorepo README: `../README.md`
- Manual testing scenarios: `../explain.md`
- `../CONTRIBUTING.md`
