# Guided onboarding & walk-through — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give new users a coherent in-app path to discover AgentForge: a checklist that reflects real progress, an optional spotlight walk-through on key screens, a dedicated “Try these flows” page aligned with the product roadmap, and a roadmap doc that matches the current backend/frontend.

**Architecture:** Keep onboarding state in `localStorage` for UX speed; derive **completion** from lightweight API reads (counts) on dashboard load and optionally on focus. Add a small `ProductTour` client component (CSS + `data-tour` targets first; optional `react-joyride` only if spotlight/tooltips need library polish). New route `/walkthrough` (or `/tutorials`) renders static use-case cards linking into the app with deep links. Roadmap edits are documentation-only but must list accurate limitations (PDF, URL ingest, webhooks).

**Tech Stack:** Next.js 15 App Router, existing `ToolShell`, `frontend/src/lib/api.ts`, Playwright for E2E, `docs/superpowers/AGENTFORGE_ROADMAP.md`.

---

## Codebase context (local)

| Area | Path | Finding |
|------|------|---------|
| API composition | `backend/app/api/v1/router.py` | Single mount for v1 (agents, knowledge, memory, webhooks, …) |
| Onboarding checklist | `frontend/src/lib/onboarding.ts` | Defines `ONBOARDING_STEPS`; **`markStepComplete` is never called** — progress bar stays at 0 unless manually edited in devtools |
| Checklist UI | `frontend/src/components/ui/OnboardingChecklist.tsx` | Renders steps; only on `dashboard/page.tsx` |
| Product scenarios | `docs/superpowers/AGENTFORGE_ROADMAP.md` | “What you can build TODAY” — **Use Case 1** still claims no PDF/URL; code has `ingest-url` + PDF in `knowledge.py` |
| Dev ergonomics | `Makefile` `quick-start` | Does not detect port **8000** collision (other projects can answer as wrong API → global “fail to fetch”) |

---

## File map (this effort)

| File | Responsibility |
|------|------------------|
| `frontend/src/lib/onboarding.ts` | Step IDs, sync helpers from API snapshot, optional tour flag in storage |
| `frontend/src/components/ui/OnboardingChecklist.tsx` | Call sync on mount; manual “Mark done” only if needed |
| `frontend/src/components/onboarding/ProductTour.tsx` (new) | Controlled steps, spotlight, keyboard dismiss |
| `frontend/src/app/walkthrough/page.tsx` (new) | Use-case cards + links |
| `frontend/src/app/dashboard/page.tsx` | `data-tour` hooks; mount `ProductTour` when flag set |
| `frontend/src/components/layout/ToolShell.tsx` or sidebar | `data-tour="nav-agents"` etc. for first tour |
| `docs/superpowers/AGENTFORGE_ROADMAP.md` | Fix limitations; add pointer to in-app `/walkthrough` |
| `README.md` | One line under Quick Start: port 8000 must be free; link `/walkthrough` |
| `Makefile` | Optional `quick-start` pre-check: warn if foreign process on 8000 |
| `frontend/e2e/onboarding.spec.ts` (new) | Playwright: checklist visible, walkthrough route 200 |

---

### Task 1: Derive onboarding completion from API (fix dead progress)

**Files:**

- Modify: `frontend/src/lib/onboarding.ts`
- Modify: `frontend/src/components/ui/OnboardingChecklist.tsx`
- Modify: `frontend/src/app/dashboard/page.tsx`

- [ ] **Step 1: Add a pure sync function** in `onboarding.ts` that maps dashboard stats → completed step IDs.

```typescript
// frontend/src/lib/onboarding.ts — add after ONBOARDING_STEPS
export type OnboardingSyncInput = {
  agents: number;
  knowledge_sources: number;
  campaigns: number;
  skills: number;
};

export function stepIdsCompletedFromStats(s: OnboardingSyncInput): string[] {
  const done: string[] = [];
  if (s.agents > 0) done.push("create_agent");
  if (s.knowledge_sources > 0) done.push("ingest_knowledge");
  if (s.campaigns > 0) done.push("run_campaign");
  if (s.skills > 0) done.push("create_skill");
  return done;
}
```

Add a sixth step to `ONBOARDING_STEPS` with `id: "create_skill"`, `href: "/skills/new"`, `cta: "New skill"` so `skills > 0` can auto-complete. Alternatively keep five steps and **omit** the `skills` line above (YAGNI).

- [ ] **Step 1b (minimal, no new API):** Extend `DashboardStats` usage from existing `/api/v1/dashboard` payload. If the response already includes `agents`, `knowledge_sources`, `campaigns`, `skills`, use those. For Forge and fine-tune, either:
  - add optional fields to dashboard backend (`forge_conversation_count`, `finetune_jobs_count`) in `backend/app/api/v1/dashboard.py` + service, **or**
  - keep steps 2 and 5 manual-only with a “I did this” button per card (stores `markStepComplete`).

Recommended YAGNI path: **auto-complete** only agents, knowledge, campaigns; **manual button** for Forge + finetune until dashboard exposes counts.

- [ ] **Step 2: In `OnboardingChecklist`,** after `useEffect` load, merge `getCompletedSteps()` with IDs from props:

```tsx
// OnboardingChecklist.tsx — add prop
export function OnboardingChecklist({ derivedComplete }: { derivedComplete?: string[] }) {
  useEffect(() => {
    setDismissed(isOnboardingDismissed());
    const manual = getCompletedSteps();
    const merged = [...new Set([...manual, ...(derivedComplete ?? [])])];
    setCompleted(merged);
  }, [derivedComplete]);
```

- [ ] **Step 3: In `dashboard/page.tsx`,** when `stats` loads, compute `derivedComplete` and pass to checklist.

```tsx
import { stepIdsCompletedFromStats } from "@/lib/onboarding";

// inside component when stats is set:
const derivedComplete = stats
  ? stepIdsCompletedFromStats({
      agents: stats.agents,
      knowledge_sources: stats.knowledge_sources,
      campaigns: stats.campaigns,
      skills: stats.skills,
    })
  : [];
// ...
<OnboardingChecklist derivedComplete={derivedComplete} />
```

- [ ] **Step 4: Manual complete for Forge / finetune**

Add two small buttons on those cards only (when not auto-derived):

```tsx
// inside map, for step.id === "open_forge" && !done
<button type="button" onClick={() => { markStepComplete("open_forge"); setCompleted(getCompletedSteps()); }} className="...">
  Mark as done
</button>
```

- [ ] **Step 5: Run frontend checks**

Run: `cd frontend && npm run lint && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/onboarding.ts frontend/src/components/ui/OnboardingChecklist.tsx frontend/src/app/dashboard/page.tsx
git commit -m "fix(frontend): sync onboarding checklist with dashboard stats"
```

---

### Task 2: Product tour (spotlight) — dashboard + nav

**Files:**

- Create: `frontend/src/components/onboarding/ProductTour.tsx`
- Modify: `frontend/src/app/dashboard/page.tsx`
- Modify: `frontend/src/components/layout/ToolShell.tsx` (or nav component — use actual sidebar file in repo)

- [ ] **Step 1: Add `data-tour` attributes** to dashboard title, onboarding section, and first nav item (inspect `ToolShell` for the correct DOM nodes).

Example:

```tsx
<h1 data-tour="dashboard-title" className="...">Mission control</h1>
<section data-tour="onboarding-card"> ... existing checklist ... </section>
```

- [ ] **Step 2: Implement `ProductTour`** with fixed steps (no npm dep in v1):

```tsx
"use client";
import { useEffect, useState } from "react";

const STEPS = [
  { selector: '[data-tour="dashboard-title"]', title: "Dashboard", body: "Metrics for agents, executions, and security." },
  { selector: '[data-tour="onboarding-card"]', body: "Complete these steps once — progress saves in the browser." },
  { selector: '[data-tour="nav-agents"]', body: "Build and run agents from here." },
];

export function ProductTour({ run }: { run: boolean }) {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  useEffect(() => {
    if (!run) return;
    const el = document.querySelector(STEPS[i]?.selector ?? "");
    if (el) setRect(el.getBoundingClientRect());
    else setRect(null);
  }, [run, i]);
  if (!run || i >= STEPS.length) return null;
  return (
    <>
      <div className="fixed inset-0 z-[100] bg-black/50" aria-hidden />
      {rect && (
        <div
          className="fixed z-[101] rounded-lg ring-2 ring-af-primary shadow-[0_0_0_9999px_rgba(0,0,0,0.5)]"
          style={{ top: rect.top - 4, left: rect.left - 4, width: rect.width + 8, height: rect.height + 8 }}
        />
      )}
      <div className="fixed bottom-8 left-1/2 z-[102] w-[min(100%,24rem)] -translate-x-1/2 rounded-xl border border-af-border bg-af-surface-container p-4 text-sm text-white shadow-xl">
        <p className="mb-2 font-bold">{STEPS[i].title ?? "Tip"}</p>
        <p className="text-af-muted">{STEPS[i].body}</p>
        <div className="mt-3 flex justify-end gap-2">
          <button type="button" className="..." onClick={() => setI((x) => x + 1)}>Next</button>
          <button type="button" className="..." onClick={() => setI(STEPS.length)}>Skip</button>
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 3: Persist “tour seen”** — `localStorage` key `af_product_tour_v1_done`; show “Start tour” button on dashboard if not done.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/onboarding/ProductTour.tsx frontend/src/app/dashboard/page.tsx frontend/src/components/layout/ToolShell.tsx
git commit -m "feat(frontend): add optional dashboard product tour"
```

---

### Task 3: `/walkthrough` page — roadmap-aligned use cases

**Files:**

- Create: `frontend/src/app/walkthrough/page.tsx`
- Modify: `frontend/src/components/layout/ToolShell.tsx` (add nav link “Walkthrough” / “Try flows”)

- [ ] **Step 1: Create page** with 5 cards mirroring roadmap sections (RAG, Schedule+webhook, Voice, Red-team, Fine-tune). Each card: goal, 3–5 bullets, primary `Link` into the app (`/knowledge`, `/agents/new`, `/campaigns`, `/finetune`, etc.).

- [ ] **Step 2: Use `ToolShell active=...`** — add a new `active` key if the type is a union; extend union in `ToolShell` props.

- [ ] **Step 3: Run** `npm run build` in `frontend` (catches type errors).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/walkthrough/page.tsx frontend/src/components/layout/ToolShell.tsx
git commit -m "feat(frontend): add walkthrough page with roadmap use cases"
```

---

### Task 4: Roadmap + README alignment

**Files:**

- Modify: `docs/superpowers/AGENTFORGE_ROADMAP.md`
- Modify: `README.md`

- [ ] **Step 1:** In “Use Case 1”, replace limitations with: PDF + URL ingest available via API/UI; note any remaining gaps (e.g. JS-heavy sites).

- [ ] **Step 2:** In “Use Case 2”, align webhook event names with `backend/app/api/v1/webhooks.py` `_ALLOWED` and `delivery.py` (document both registered events and extra lifecycle if emitted).

- [ ] **Step 3:** Add at top of roadmap: **In-app guide:** `/walkthrough`.

- [ ] **Step 4:** README Quick Start — bullet “Ensure port 8000 is free (`lsof -i :8000`)” and link `/walkthrough`.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/AGENTFORGE_ROADMAP.md README.md
git commit -m "docs: align roadmap with product and link walkthrough"
```

---

### Task 5: Dev ergonomics — port collision warning

**Files:**

- Modify: `Makefile`

- [ ] **Step 1:** Before starting uvicorn in `quick-start`, print warning if `lsof -i :8000` returns PIDs not matching current shell (portable check: `lsof -ti :8000` non-empty → `echo "WARNING: something already listens on 8000"`). Do **not** auto-kill by default (surprise for users running multiple stacks).

```makefile
quick-start: dev-ready
	@if lsof -ti :8000 >/dev/null 2>&1; then echo "WARNING: port 8000 is in use — AgentForge API may not be reachable at http://localhost:8000"; fi
	@echo "Lancement du backend et du frontend en local..."
```

- [ ] **Step 2: Commit**

```bash
git add Makefile
git commit -m "chore(make): warn when port 8000 is already in use"
```

---

### Task 6: Playwright smoke for walkthrough + checklist

**Files:**

- Create: `frontend/e2e/walkthrough.spec.ts` (or under `frontend/tests/e2e` if that is the repo convention — **use the same folder as existing Playwright tests**)

- [ ] **Step 1: Locate existing Playwright config** (`playwright.config.ts` in `frontend`).

- [ ] **Step 2: Write test** — login fixture if required, then:

```typescript
import { test, expect } from "@playwright/test";

test("walkthrough page renders use case headings", async ({ page }) => {
  await page.goto("/walkthrough");
  await expect(page.getByRole("heading", { name: /walkthrough|try these/i })).toBeVisible();
});
```

- [ ] **Step 3: Run** `cd frontend && npx playwright test walkthrough.spec.ts`

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/walkthrough.spec.ts
git commit -m "test(e2e): cover walkthrough page load"
```

---

## Proposed improvements (backlog, not all in this plan)

| Item | Rationale |
|------|-----------|
| Extend `GET /api/v1/dashboard` with `forge_conversations`, `finetune_jobs` counts | Fully auto onboarding without manual “Mark done” |
| `react-joyride` or `@reactour/tour` | Accessibility + mobile-friendly tours if custom overlay is insufficient |
| Builder-specific tour (`data-tour` on React Flow palette) | Highest drop-off area for new users |
| Server-side `user_preferences.onboarding` | Sync across devices (optional) |
| Forge slash `/walkthrough` command | Already pattern in README; wire to open `/walkthrough` in-app |
| **Agent Builder (React Flow) — UI pro & cohérence design** | Refonte visuelle du canvas et des contrôles du builder (`frontend/src/app/agents/[id]/builder/page.tsx`, `frontend/src/components/builder/InspectorPanel.tsx`, `CollabCursors.tsx`) : nœuds et handles plus lisibles, états sélection / hover / erreur, edges et labels, minimap / controls (`@xyflow/react`), panneau inspecteur (typo, espacements, `af-*`), palette d’ajout de nœuds, empty states. Objectif : rendu **plus beau, plus professionnel, aligné** avec le reste de l’app (dashboard, Forge). **Hors périmètre des Tasks 1–6** ; chantier UI dédié après onboarding / walkthrough. |

### Agent Builder / React Flow (détail — backlog UI)

- **Nœuds** : hiérarchie visuelle (titre, type, icône), bordures et ombres cohérentes, distinction claire LLM / Tool / mémoire / voix.
- **Edges** : courbes lisibles, couleur selon état (conditionnel), labels si besoin sans surcharger.
- **Chrome React Flow** : `Background`, `Controls`, `MiniMap` — couleurs et opacités harmonisées avec le thème sombre AgentForge.
- **Panneau latéral / inspecteur** : grille, champs, validation visuelle des configs JSON ou formulaires.
- **Accessibilité** : focus clavier sur la palette et les actions critiques ; tooltips pour les icônes du toolbar.
- **Responsive** : largeur minimale du canvas sur petit écran, scroll du panneau sans casser le graphe.

---

## Self-review

**1. Spec coverage:** Walk-through UI, use cases on front, roadmap coherence, onboarding progress bug — each mapped to Task 1–6. **Agent Builder (React Flow) UI polish** is explicit backlog (design), not part of Tasks 1–6.
**2. Placeholder scan:** No `TBD`; optional paths explicitly named (joyride deferred).
**3. Type consistency:** `OnboardingSyncInput` fields must match `DashboardStats` in `dashboard/page.tsx` — verify names (`knowledge_sources` vs `knowledge` etc.) before implementing Task 1.

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-10-guided-onboarding-walkthrough.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session with checkpoints between tasks.

**Which approach do you want?**

---

## Sources (repo)

- `frontend/src/lib/onboarding.ts`, `frontend/src/components/ui/OnboardingChecklist.tsx`, `frontend/src/app/dashboard/page.tsx`, `frontend/src/app/agents/[id]/builder/page.tsx` (builder / React Flow)
- `backend/app/api/v1/router.py`, `backend/app/api/v1/knowledge.py`, `backend/app/api/v1/webhooks.py`
- `docs/superpowers/AGENTFORGE_ROADMAP.md`
