# Phase N4 — OAuth Google + scheduling d'exécutions

> **Statut : terminé** (mars 2026). Spec source : `docs/superpowers/specs/2026-03-30-agentforge-roadmap-design.md` § Phase N4.

> **For agentic workers:** `superpowers:subagent-driven-development` ou `superpowers:executing-plans` ; vérifier auth existante avant de brancher Google.

---

## 1. OAuth Google

### 1.1 Données

- [x] Migration Alembic : table `social_accounts`
  `id`, `user_id` (FK users), `provider`, `provider_id`, `email`, tokens chiffrés, `expires_at` (TIMESTAMPTZ). Voir `backend/migrations/versions/014_social_accounts_oauth.py`.
- [x] Index unique `(provider, provider_id)` et `(user_id, provider)`.
- [x] Chiffrement at rest pour tokens (`token_cipher` dérivé de `JWT_SECRET_KEY`).

### 1.2 Backend

- [x] Config : `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI` dans `.env.example`.
- [x] `GET /api/v1/auth/oauth/google` — redirect vers consent Google (PKCE + state JWT).
- [x] `GET /api/v1/auth/oauth/google/callback` — échange code, upsert `social_accounts`, émission JWT AgentForge.
- [x] Règle : email Google déjà présent → lier au `user` existant (pas de doublon).

### 1.3 Frontend

- [x] Bouton « Continuer avec Google » sur `/login` et `/register` (redirect full-page).
- [x] Page `frontend/src/app/auth/callback/page.tsx` (hash tokens).
- [x] Gestion erreur OAuth côté UX (refus, state invalide — messages API / redirect).

### 1.4 Tests

- [x] Tests unitaires flux OAuth (mock httpx) : `backend/tests/test_google_oauth.py`.
- [ ] Test e2e Playwright OAuth (optionnel CI) — **non prioritaire**.

---

## 2. Scheduling d'exécutions

### 2.1 Données

- [x] Migration : table `agent_schedules` + `trigger_source` / `schedule_id` sur exécutions. Voir `013_agent_schedules`.

### 2.2 Backend

- [x] CRUD : `POST/GET/PATCH/DELETE /api/v1/agents/{id}/schedules` (auth + ownership).
- [x] Calcul `next_run_at` (croniter ou équivalent).
- [x] Worker : `backend/app/infrastructure/scheduling/tick.py` (boucle asyncio).
- [x] Persistance : `trigger_source` = `schedule` sur les exécutions déclenchées par cron.

### 2.3 SDK Python (`agentforge-client`)

- [x] `SchedulesAPI` : `sdk-client/src/agentforge_client/schedules.py`, exposé sur `AgentforgeClient.schedules`.

### 2.4 Frontend

- [x] Section **Schedules (cron)** sur fiche agent : création, liste, toggle `enabled`, suppression, lien exécutions.

### 2.5 Tests

- [x] Tests unitaires / intégration ciblés selon codebase (à étendre si besoin : `freezegun` sur tick — **backlog léger**).

---

## Critères d'acceptation (rappel)

- [x] Login Google → JWT valide → accès app.
- [x] Schedule créé → worker peut déclencher → exécutions avec origine schedule.
- [x] `client.schedules.create()` aligné sur l’API REST.
