# AgentForge — Polish produit, chat omnicanal & motion globale (plan v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finaliser l’alignement backend (modèles, température, tests), et élever le frontend : chat accessible et cohérent sur toutes les surfaces utiles, animations globales sobres et accessibles (`prefers-reduced-motion`), sans régresser la perf ni la stack (CSS-first, pas de nouvelle dépendance lourde).

**Architecture:** Backend inchangé dans ses principes (FastAPI + orchestrateur). Frontend : enrichir `ChatContext` (persistance agent, raccourci clavier), renforcer `ChatSlideOver` / `FloatingChatButton` (a11y, transitions), centraliser les tokens de motion dans `globals.css`, appliquer des utilitaires réutilisables sur cartes et navigation. Google OAuth Gmail/Calendar est **assumé configuré** par l’utilisateur — ne reste qu’une smoke checklist.

**Tech Stack:** FastAPI, SQLAlchemy async, Next.js 15 App Router, React 19, Tailwind v4 `@theme`, pas de Framer Motion dans le repo (animer en CSS + `transition`).

---

## État des lieux (avril 2026)

### Déjà en place

| Zone | Fichiers / détail |
|------|-------------------|
| Chat global | `frontend/src/contexts/ChatContext.tsx`, `components/chat/ChatSlideOver.tsx`, `FloatingChatButton.tsx`, `ClientProviders.tsx` |
| Masquage FAB sur `/chat` | `FloatingChatButton.tsx` (`pathname === "/chat"`) |
| Playground skills | `POST /api/v1/skills/seed-defaults`, bouton dans `sandbox/page.tsx` |
| Builder | Suppression nœud, panneau model + température, `saveGraph` |
| Export enrichi | `sdk_usage` dans `backend/app/api/v1/agents.py` |
| Orchestrateur | `temperature` depuis `node_config` si présent (`langgraph_orchestrator.py`) |

### Google / Gmail / Calendar

**Statut : complété côté utilisateur (console + scopes + reconnect).**
Les tâches code restantes ne portent plus sur la création du client OAuth ; seule une **vérification fonctionnelle** (Task 6) reste recommandée.

### Écarts à traiter (priorisés)

| Priorité | Sujet |
|----------|--------|
| P0 | `default_agents.py` : encore `gemini-2.5-flash` / `gpt-4o-mini` sur plusieurs agents |
| P0 | Température au niveau **agent** non fusionnée dans le LLM si absent du nœud |
| P1 | Tests API `seed-defaults` + import invalide |
| P1 | Chat : dernier agent non persisté, pas de raccourci global, triggers manquants (dashboard, cartes agents) |
| P1 | Motion : peu d’animations cohérentes ; pas de garde `prefers-reduced-motion` globale |
| P2 | Agent calendrier / interview seed + page `/chat` alignée visuellement sur le slide-over |

---

## File map

| Fichier | Rôle |
|---------|------|
| `backend/app/domain/default_agents.py` | Modèles seed + agent calendrier éventuel |
| `backend/app/infrastructure/orchestration/langgraph_orchestrator.py` | Fusion `model_config.temperature` |
| `frontend/src/app/agents/new/page.tsx` | Identifiants modèles création agent |
| `frontend/src/contexts/ChatContext.tsx` | Persistance `localStorage`, raccourci clavier (ou module dédié) |
| `frontend/src/components/chat/ChatSlideOver.tsx` | Focus trap, Escape, transitions panel/backdrop |
| `frontend/src/components/chat/FloatingChatButton.tsx` | Animation d’entrée, `aria-label` |
| `frontend/src/app/globals.css` | `@keyframes`, utilitaires `.af-*-motion`, reduced-motion |
| `frontend/src/app/dashboard/page.tsx` | Boutons « Ouvrir le chat » sur lignes récentes / CTA |
| `frontend/src/app/agents/page.tsx` | `openChat(id)` sur chaque carte si pas déjà partout |
| `frontend/src/app/chat/page.tsx` | Parité visuelle avec slide-over (tokens, suggestions) |
| `backend/tests/test_agent_skills.py` ou nouveau fichier | Tests seed-defaults / import |

---

### Task 1: Aligner les modèles seed (`default_agents.py`)

**Files:**
- Modify: `backend/app/domain/default_agents.py`

- [x] **Step 1:** Exécuter et corriger selon sortie :

```bash
grep -n 'gemini-2.5-flash\|gpt-4o-mini' backend/app/domain/default_agents.py
```

Remplacer par `gemini-3-flash` et `gpt-5.4-mini` pour tous les agents non-`mock`.

- [x] **Step 2:**

```bash
cd backend && uv run ruff check app/domain/default_agents.py && uv run ruff format app/domain/default_agents.py
```

- [ ] **Step 3:** Commit

```bash
git add backend/app/domain/default_agents.py
git commit -m "fix(backend): align default agent model ids with gemini-3-flash and gpt-5.4-mini"
```

---

### Task 2: Température agent-level dans l’orchestrateur

**Files:**
- Modify: `backend/app/infrastructure/orchestration/langgraph_orchestrator.py`
- Read: `backend/app/application/services/agent_service.py` (passage de `model_config` au run)

- [x] **Step 1:** Lors de la construction du modèle LLM par nœud, si `node_config.get("temperature")` est absent et que `agent_model_config.get("temperature")` est présent, utiliser la valeur agent. *(Déjà le cas : `_merge_node_model_config` part de `dict(agent_model_config)` puis ne remplace `temperature` que si le nœud la fournit.)*

- [x] **Step 2:** Ajouter ou étendre un test dans `backend/tests/` (ex. test orchestrateur ou graph existant) qui assert la température effective. *(Ajout : `tests/test_merge_node_model_config.py`.)*

- [ ] **Step 3:**

```bash
cd backend && uv run pytest tests/ -q --no-cov --tb=short -k "orchestr or graph" 2>&1 | tail -20
```

(Ajuster `-k` au fichier réellement touché.)

- [ ] **Step 4:** Commit

```bash
git commit -m "fix(backend): apply agent model_config temperature when llm node omits it"
```

---

### Task 3: Frontend « new agent » — identifiants modèles

**Files:**
- Modify: `frontend/src/app/agents/new/page.tsx`

- [x] **Step 1:**

```bash
grep -n 'gpt-4o-mini\|gemini-2.5' frontend/src/app/agents/new/page.tsx
```

Remplacer par `gpt-5.4-mini` / `gemini-3-flash` (et tout libellé utilisateur cohérent). *(Aucune occurrence restante.)*

- [x] **Step 2:**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3:** Commit

```bash
git commit -m "fix(frontend): sync new-agent defaults with current model identifiers"
```

---

### Task 4: Tests API — `seed-defaults` & import agent

**Files:**
- Modify: `backend/tests/test_agent_skills.py` ou Create: `backend/tests/test_skills_seed_defaults.py`
- Modify: tests couvrant `POST /api/v1/agents/import` si fichier dédié

- [x] **Step 1:** Test authentifié : premier `POST /api/v1/skills/seed-defaults` → 201, clé `count` présente ; second appel → idempotent (`count` 0 ou faible).

- [x] **Step 2:** Test `POST /api/v1/agents/import-bundle` avec corps `{ "agentforge_version": "2.0", "agent": {} }` → 400, message explicite.

- [ ] **Step 3:**

```bash
cd backend && uv run pytest tests/test_agent_skills.py tests/test_auth_agents.py -q --no-cov --tb=short
```

(Étendre la liste si nouveaux fichiers.)

- [ ] **Step 4:** Commit

```bash
git commit -m "test: cover skills seed-defaults and agent import validation"
```

---

### Task 5: Agent seed « calendrier / interview » (optionnel)

**Files:**
- Modify: `backend/app/domain/default_agents.py`
- Verify noms dans `backend/app/domain/skill_templates.py` : `read_calendar`, `create_calendar_event` (ou équivalent)

- [x] **Step 1:** Ajouter un agent du type *Secrétaire calendrier* avec prompt court : agir sans demander confirmation inutile si la consigne est claire ; ne pas inventer de créneaux ; utiliser les outils Google si connectés. *(Déjà présent dans `default_agents.py`.)*

- [x] **Step 2:** Attacher uniquement des skills qui existent dans `SKILL_TEMPLATES`.

- [ ] **Step 3:** Commit

```bash
git commit -m "feat(backend): add calendar-focused default agent with proactive prompt"
```

---

### Task 6: Google — vérification post-config (utilisateur a fini l’OAuth)

**Statut configuration : fait par Nico.** Aucun code requis sauf si un endpoint de santé manque.

- [ ] **Step 1:** Depuis l’app connectée, exécuter un agent avec tool `read_calendar` ou équivalent → réponse non vide ou erreur **401/403** explicite (pas 500).

- [ ] **Step 2:** Si 403 : re-vérifier scopes sur le token (re-login Settings).

- [ ] **Step 3:** Documenter en une ligne dans `AGENTS.md` ou commentaire équipe : « Google Gmail+Calendar : scopes listés dans config OAuth » — **uniquement si** le repo impose une trace ; sinon cocher cette étape comme validation manuelle sans commit.

---

### Task 7: E2E vocal & finetune (manuel)

- [ ] **Vocal:** Graphe ASR (Whisper) → LLM → TTS (OpenAI), `OPENAI_API_KEY`, entry = ASR. Succès : audio retour sans 500.

- [ ] **Finetune:** `MODAL_ENABLED=true` + `modal deploy` sur l’app train du repo. Succès : job progresse dans l’UI/API.

---

### Task 8: Chat dynamique partout (contexte, raccourci, triggers UI)

**Files:**
- Modify: `frontend/src/contexts/ChatContext.tsx`
- Modify: `frontend/src/components/chat/FloatingChatButton.tsx`
- Modify: `frontend/src/components/chat/ChatSlideOver.tsx`
- Modify: `frontend/src/app/dashboard/page.tsx`
- Modify: `frontend/src/app/agents/page.tsx` (si besoin de `openChat` additionnel)

- [x] **Step 1 — Persistance du dernier agent**

Dans `ChatProvider`, clé `localStorage` `af_last_chat_agent_id` :

```tsx
const STORAGE_KEY = "af_last_chat_agent_id";

// Au montage (useEffect, client-only):
const raw = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
// Si raw est un UUID valide, initialiser selectedAgentId

// Lors de setSelectedAgentId(id) ou openChat(agentId):
if (id && typeof window !== "undefined") localStorage.setItem(STORAGE_KEY, id);
```

Envelopper `setSelectedAgentId` dans un `useCallback` qui écrit le storage.

- [x] **Step 2 — Raccourci clavier global**

Dans `ChatProvider` (ou petit hook `useGlobalChatShortcut` importé une seule fois) :

```tsx
useEffect(() => {
  const onKey = (e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "j") {
      e.preventDefault();
      setIsOpen((o) => !o);
    }
  };
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}, []);
```

Afficher l’indice `⌘J` / `Ctrl+J` dans le tooltip du FAB ou le footer du slide-over.

- [x] **Step 3 — Accessibilité slide-over**

Dans `ChatSlideOver` : `role="dialog"`, `aria-modal="true"`, `aria-labelledby` sur le titre ; **Escape** appelle `closeChat()` ; focus trap basique (cycle Tab entre éléments `[tabindex]:not([disabled])` du panneau) quand `isOpen`.

- [x] **Step 4 — Triggers dashboard**

Sur `dashboard/page.tsx`, pour chaque ligne `recent_executions` : bouton icône chat qui fait `openChat(row.agent_id)` (importer `useChatContext`).

- [x] **Step 5 — Typecheck + commit** *(tsc OK ; commit à faire côté repo)*

```bash
cd frontend && npx tsc --noEmit
```

```bash
git commit -m "feat(frontend): persist last chat agent, global shortcut, a11y and dashboard chat triggers"
```

---

### Task 9: Animations globales du site (CSS, accessible)

**Files:**
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/src/components/layout/AppHeader.tsx` (optionnel : transition lien actif)
- Modify: `frontend/src/app/agents/page.tsx` (optionnel : `af-hover-lift` sur cartes)

- [x] **Step 1 — Reduced motion**

Dans `globals.css`, après `@layer utilities` ou dans `@layer base` :

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [x] **Step 2 — Keyframes + utilitaires**

```css
@keyframes af-fade-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.af-motion-fade-in {
  animation: af-fade-in 0.35s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.af-hover-lift {
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}
.af-hover-lift:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 40px -12px rgba(195, 192, 255, 0.15);
}
```

- [x] **Step 3 — Brancher le FAB**

Sur le `<button>` du `FloatingChatButton`, ajouter `className="... af-motion-fade-in"` (en conservant les classes existantes).

- [x] **Step 4 — Cartes agents**

Sur le conteneur de carte dans `agents/page.tsx`, ajouter `af-hover-lift` (une seule couche, pas de refonte layout).

- [x] **Step 5:** *(tsc OK ; commit à faire)*

```bash
cd frontend && npx tsc --noEmit
```

```bash
git commit -m "feat(frontend): global motion utilities, reduced-motion guard, card hover polish"
```

---

### Task 10: Page `/chat` — parité visuelle avec le slide-over

**Files:**
- Modify: `frontend/src/app/chat/page.tsx`

- [x] **Step 1:** Réutiliser les mêmes classes de bulles / sidebar / suggestion chips que `ChatSlideOver` (factoriser en `components/chat/ChatMessageBubble.tsx` **seulement si** duplication > ~40 lignes ; sinon dupliquer minimalement pour rester YAGNI).

- [x] **Step 2:** Ajouter rappel du raccourci `⌘J` / `Ctrl+J` dans le footer ou sous le header de page.

- [x] **Step 3:**

```bash
cd frontend && npx tsc --noEmit
```

```bash
git commit -m "feat(frontend): align full chat page styling with slide-over and shortcut hint"
```

---

## Self-review

1. **Couverture:** Backend P0 (Tasks 1–2), frontend new agent (3), tests (4), calendrier seed (5), Google smoke (6), E2E manuel (7), chat omnicanal (8), motion (9), `/chat` (10).
2. **Placeholders:** Aucun « TBD » ; étapes avec commandes et extraits concrets.
3. **Cohérence:** Pas d’ajout de Framer Motion ; une seule touche storage pour l’agent chat.

---

## Execution handoff

**Plan:** `docs/superpowers/plans/2026-04-01-product-polish-google-voice-e2e.md` (v2)

**Options:**

1. **Subagent-Driven (recommandé)** — un sous-agent par task, review entre tasks.
2. **Inline** — enchaîner Tasks 1→10 dans une session avec checkpoints après 4 et 9.

**Quelle approche ?**
