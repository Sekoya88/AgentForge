# AgentForge — Roadmap & améliorations (reste à faire)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prioriser et détailler tout le travail restant : fiabilité chat/API/Google, polish frontend (lisibilité, gradients, animations cohérentes, accessibilité), puis backlog produit (Track C, speech prod).

**Architecture:** Les chantiers P0 corrigent les contrats données (messages assistant normalisés, traces d’exécution). Le polish UI s’appuie sur les tokens `@theme` existants (`globals.css`), les utilitaires `.af-*`, et les composants layout/chat déjà en place — sans ajouter de dépendance animation lourde (CSS-first, `prefers-reduced-motion` déjà global dans `globals.css` lignes 75–83).

**Tech Stack:** FastAPI, Pydantic v2, Next.js App Router, Tailwind CSS v4 `@theme`, specs de référence `docs/superpowers/specs/2026-03-30-agentforge-roadmap-design.md`.

**Référence lecture seule:** historique des livraisons passées = `git log` / spec § phases — ce document ne liste que l’avenir.

---

## Carte des fichiers (front — base actuelle)

| Fichier | Rôle aujourd’hui |
|---------|------------------|
| `frontend/src/app/globals.css` | Tokens `--color-af-*`, mesh aurora `.af-aurora-mesh`, blobs, keyframes drift, utilitaires `.af-card`, `.af-motion-fade-in`, reduced-motion |
| `frontend/src/components/layout/AuroraBackground.tsx` | Trois blobs + mesh plein écran |
| `frontend/src/components/layout/ToolShell.tsx` | Chrome navigation |
| `frontend/src/components/chat/ChatSlideOver.tsx` | Panneau chat global |
| `frontend/src/components/chat/FloatingChatButton.tsx` | FAB |
| `frontend/src/app/chat/page.tsx` | Chat plein écran |
| `frontend/src/contexts/ChatContext.tsx` | État agent sélectionné, ouverture |
| `frontend/src/app/dashboard/page.tsx` | Dashboard |
| `frontend/src/app/agents/page.tsx` | Liste agents |
| `frontend/src/app/sandbox/page.tsx` | Playground / templates |

---

## Task 1: Normaliser les messages assistant à la frontière API (P0)

**Problème:** `ExecutionResponse.output_messages` est typé `list[Any]` dans `backend/app/api/schemas/agent_schemas.py` (~l.134–135) : la sérialisation JSON peut renvoyer des blocs bruts (`type`/`text`/…) même si le domaine sait les coercer.

**Files:**
- Modify: `backend/app/api/schemas/agent_schemas.py`
- Modify: `backend/app/api/v1/agents.py` (`_exec_to_response` si besoin de mapper explicitement)
- Read: `backend/app/domain/value_objects.py` (`MessageDict`)
- Test: `backend/tests/test_execution_response_messages.py` (nouveau)

- [ ] **Step 1: Test — réponse avec contenu liste doit sortir en string**

```python
from uuid import uuid4

from app.api.schemas.agent_schemas import ExecutionResponse


def test_execution_response_coerces_list_content_to_text():
    raw = {
        "id": uuid4(),
        "agent_id": uuid4(),
        "user_id": uuid4(),
        "thread_id": "t1",
        "status": "completed",
        "input_messages": [],
        "output_messages": [
            {"role": "assistant", "content": [{"type": "text", "text": "Bonjour"}]},
        ],
        "interrupt_state": None,
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:00:01Z",
        "token_usage": None,
        "duration_ms": 1,
    }
    m = ExecutionResponse.model_validate(raw)
    assert m.output_messages is not None
    assert m.output_messages[0]["content"] == "Bonjour"
```

- [ ] **Step 2:** Lancer `cd backend && uv run pytest tests/test_execution_response_messages.py -v` — attendu **FAIL** tant que le modèle n’impose pas la coercion.

- [ ] **Step 3:** Introduire un modèle `AssistantMessageOut` (ou réutiliser `MessageDict` en mode sérialisation) avec validateur `field_validator` sur `content` appelant `coerce_message_content_to_str` depuis `app.domain.message_content`.

- [ ] **Step 4:** Typer `output_messages` (et idéalement `input_messages`) avec ce modèle dans `ExecutionResponse` ; ajuster `_exec_to_response` pour passer par `model_validate` si nécessaire.

- [ ] **Step 5:** `uv run pytest tests/test_execution_response_messages.py -v` — attendu **PASS**.

- [ ] **Step 6:** Commit `fix(api): coerce execution message content in ExecutionResponse`

---

## Task 2: Mémoire multi-tours & exécutions vides (P0 — vérif + correctifs ciblés)

**Files:**
- Read: `backend/app/application/services/agent_service.py` (`_merge_thread_context_messages`, `list_executions_for_thread`)
- Read: `frontend/src/app/chat/page.tsx`, `frontend/src/components/chat/ChatSlideOver.tsx` (passage `conv.thread_id`)
- Read: `frontend/src/lib/sse.ts` ou équivalent consommation SSE

- [ ] **Step 1:** Reproduire localement : créer une conversation, envoyer 2 messages, vérifier dans Network que le POST `/execute` envoie le **même** `thread_id` que `GET /conversations`.

- [ ] **Step 2:** Si le thread change : tracer `activeConversation` après `listConversations` (race / reset d’état) et corriger la synchro d’état React.

- [ ] **Step 3:** Pour réponses vides : si `GET /agents/{id}/executions/{exec_id}` a `output_messages` null ou assistant sans texte, logger côté backend au moment du `update_execution` et exposer `status`/`error` si applicable.

- [ ] **Step 4:** Côté UI, afficher un message d’erreur lisible quand `status === "failed"` ou contenu assistant vide après stream terminé (au lieu de « (empty) » silencieux).

- [ ] **Step 5:** Commit au fil de l’eau (`fix(chat): …` / `fix(backend): …`).

---

## Task 3: Google Calendar / Gmail — fiabilité outils (P0)

**Files:**
- Read: `backend/app/application/services/google_oauth_runtime.py`
- Read: `backend/app/infrastructure/integrations/google_api_service.py`
- Read: `backend/app/infrastructure/orchestration/langgraph_orchestrator.py` (boucle outils Gemini)

- [ ] **Step 1:** Checklist manuelle documentée dans `docs/superpowers/specs/` ou commentaire court dans ce plan (révision suivante) : scopes attendus, reconnexion OAuth, test `create_calendar_event` seul via sandbox.

- [ ] **Step 2:** Ajouter test d’intégration mocké ou test de contrat sur le schéma d’appel outil (si absent).

- [ ] **Step 3:** Commit `test(backend): …` ou `fix(google): …` selon constat.

---

## Task 4: Lisibilité & hiérarchie typographique (P1 — frontend)

**Objectif:** Corps de l’app en **sans-serif** (`--font-sans` / Space Grotesk) pour le contenu UI ; réserver **mono** aux IDs, logs, code. Augmenter légèrement contraste des textes secondaires sans casser la palette « dark premium ».

**Files:**
- Modify: `frontend/src/app/globals.css` (`@layer base` body, tokens `--color-af-muted*`)
- Modify: `frontend/src/components/layout/ToolShell.tsx` (si titres trop légers)
- Modify: `frontend/src/app/chat/page.tsx`, `ChatSlideOver.tsx` (tailles `text-sm` / `leading` / `text-af-muted`)

- [ ] **Step 1:** Dans `globals.css`, sur `body`, remplacer `font-mono` par `font-sans` pour le texte global ; ajouter une classe utilitaire `.af-mono` pour les zones techniques.

```css
@layer base {
  body {
    @apply bg-af-bg text-af-on-surface font-sans antialiased selection:bg-af-primary/30;
  }
}
```

- [ ] **Step 2:** Passer en revue `chat/page.tsx` et `ChatSlideOver.tsx` : bulles utilisateur / assistant avec `leading-relaxed` (déjà partiellement) et contraste minimum WCAG approximatif sur `text-af-muted` vs fond (ajuster `--color-af-muted` de `#8888aa` → valeur légèrement plus claire si besoin, ex. `#9b9bb8`).

- [ ] **Step 3:** Vérifier visuellement `/chat`, `/dashboard`, `/agents` en navigation réelle.

- [ ] **Step 4:** Commit `style(frontend): improve default typography and muted contrast`

---

## Task 5: Gradients Aurora plus clairs et moins « boueux » (P1 — frontend)

**Objectif:** Garder l’ambiance mais **séparer** mieux les plans : mesh plus doux, blobs avec opacités et teintes plus lisibles (moins de mélange indigo+violet+teal au même niveau d’intensité).

**Files:**
- Modify: `frontend/src/app/globals.css` (`.af-aurora-mesh`, `radial-gradient` rgba, keyframes `af-aurora-mesh-shift`)
- Modify: `frontend/src/components/layout/AuroraBackground.tsx` (opacités `opacity-[0.xx]`)

- [ ] **Step 1:** Réduire l’opacité du mesh global (ex. multiplier les alpha par ~0.65–0.8) et resserrer les stops `transparent` pour éviter le voile gris sur le contenu.

Proposition de remplacement des trois lignes `background:` dans `.af-aurora-mesh` (à ajuster à l’œil) :

```css
.af-aurora-mesh {
  background:
    radial-gradient(ellipse 75% 45% at 50% -15%, rgba(79, 70, 229, 0.14), transparent 58%),
    radial-gradient(ellipse 55% 38% at 95% 45%, rgba(124, 58, 237, 0.09), transparent 52%),
    radial-gradient(ellipse 45% 32% at 5% 85%, rgba(45, 212, 191, 0.07), transparent 48%);
}
```

- [ ] **Step 2:** Diminuer `hue-rotate` max dans `@keyframes af-aurora-mesh-shift` (ex. `22deg` → `12deg`) pour limiter la dérive vers des verts/gris.

- [ ] **Step 3:** Dans `AuroraBackground.tsx`, baisser les opacités des blobs (ex. `0.16` → `0.10`, `0.11` → `0.07`, `0.12` → `0.08`) ou augmenter le `blur` via une classe si le contour reste trop net.

- [ ] **Step 4:** Vérifier avec **Réduire les animations** OS : le bloc `@media (prefers-reduced-motion: reduce)` doit toujours figer le mouvement (déjà en place).

- [ ] **Step 5:** Commit `style(frontend): soften aurora mesh and blob contrast`

---

## Task 6: Système de motion cohérent (P1 — frontend)

**Objectif:** Même courbe, mêmes durées pour entrées de panneau, cartes, FAB ; éviter les `transition-all` trop larges sur des éléments lourds.

**Files:**
- Modify: `frontend/src/app/globals.css` (nouveaux utilitaires)
- Modify: `frontend/src/components/chat/ChatSlideOver.tsx` (`transition-*`, `duration-300`)
- Modify: `frontend/src/components/chat/FloatingChatButton.tsx`
- Modify: `frontend/src/app/dashboard/page.tsx`, `frontend/src/app/agents/page.tsx`

- [ ] **Step 1:** Définir des variables CSS dans `@theme` ou `:root` :

```css
:root {
  --af-motion-enter: 280ms cubic-bezier(0.22, 1, 0.36, 1);
  --af-motion-standard: 200ms ease;
}
```

- [ ] **Step 2:** Ajouter `.af-panel-enter` (translate + opacity) pour le slide-over, réutilisé sur le backdrop.

- [ ] **Step 3:** Remplacer les durées arbitraires dispersées (`200`, `300`, `500`) par `var(--af-motion-enter)` là où c’est une entrée modale / drawer.

- [ ] **Step 4:** S’assurer qu’aucune animation critique pour la compréhension ne dépend du seul mouvement (pas d’information uniquement en hover animé).

- [ ] **Step 5:** Commit `style(frontend): unify motion tokens for chat and shell`

---

## Task 7: Chat omnicanal & parité `/chat` vs slide-over (P1)

**Files:**
- Modify: `frontend/src/contexts/ChatContext.tsx` (persistance `localStorage` clé par user ou `af-selected-agent-id`)
- Modify: `frontend/src/app/dashboard/page.tsx`, `frontend/src/app/agents/page.tsx` (boutons `openChat(agentId)`)
- Modify: `frontend/src/app/chat/page.tsx` (tokens alignés sur slide-over : espacements, suggestions, header)

- [ ] **Step 1:** Persister `selectedAgentId` au changement ; relire au mount.

- [ ] **Step 2:** Cartes dashboard / agents : une action visible « Chat » qui appelle `openChat(id)`.

- [ ] **Step 3:** Comparer visuellement les deux surfaces et factoriser classes communes si duplication importante (optionnel : petit module `chatStyles` ou classes partagées).

- [ ] **Step 4:** Commit `feat(frontend): persist chat agent and expand open-chat entry points`

---

## Task 8: Playground — compare variants & catalogue (P1)

**Files:**
- Modify: `frontend/src/app/sandbox/page.tsx`
- Read: `frontend/src/lib/api.ts` (`compareAgents` ou équivalent)
- Read: `backend/app/api/v1/agents.py` (`POST /compare`)

- [ ] **Step 1:** UI pour lancer 2–4 variantes avec labels + overrides (température, etc.) et afficher les `execution_id` / liens vers streams SSE.

- [ ] **Step 2:** Vérifier que le catalogue templates et l’install skill restent accessibles après navigation.

- [ ] **Step 3:** Commit `feat(frontend): sandbox compare variants panel`

---

## Task 9: Tests API complémentaires (P1 backend)

**Files:**
- Modify ou create: `backend/tests/test_agent_skills.py` ou fichier dédié

- [ ] **Step 1:** Couvrir `POST .../seed-defaults` (succès + idempotence minimale).

- [ ] **Step 2:** Couvrir import bundle invalide (réponse 4xx attendue).

- [ ] **Step 3:** Commit `test(backend): seed-defaults and import error paths`

---

## Task 10: Speech — hors MVP (P2)

**Files:**
- Doc: `docs/superpowers/specs/2026-03-30-agentforge-roadmap-design.md` (section speech) ou `README` Modal
- Modify: `backend/modal_functions/train_speech.py` (quand priorisé)

- [ ] **Step 1:** Documenter variables d’env HF / quotas / coûts Modal.

- [ ] **Step 2:** Remplacer stubs par entraînement réel selon priorité produit.

- [ ] **Step 3:** Commit / PR dédiés.

---

## Task 11: Track C — backlog transverse (P2+)

Réf. spec § Track C. Découper en plans datés `docs/superpowers/plans/YYYY-MM-DD-C1-….md` quand une vague démarre.

| Vague | Livrables cibles |
|-------|------------------|
| **C1** | Multimodal, Anthropic, embeddings Ollama, RAG |
| **C2** | Skills natifs (`web_search`, …), MCP, memory node, galerie templates |
| **C3** | Langfuse avancé, evals, diff de versions, Sentry |
| **C4** | Notifications, multi-tenant |
| **C5** | Checkpointer Postgres HITL, CLI watch, streaming fin, budgets |

- [ ] **Step 1:** Choisir une vague ; rédiger un plan daté séparé (writing-plans) avant code.

---

## Self-review (writing-plans)

| Critère | Statut |
|---------|--------|
| Spec coverage P0/P1 front | Tâches 1–9 mappent fiabilité, API, UI, playground, tests |
| Placeholders | Aucun « TBD » ; code d’exemple concret pour tests et CSS |
| Cohérence des noms | `ExecutionResponse`, `MessageDict`, chemins fichiers alignés repo |

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-01-agentforge-roadmap.md`. Two execution options:**

1. **Subagent-Driven (recommended)** — un sous-agent par tâche, revue entre tâches
2. **Inline execution** — enchaîner les tâches dans la même session avec checkpoints

**Which approach?**
