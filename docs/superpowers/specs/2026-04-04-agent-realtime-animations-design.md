# Agent Real-Time Animations — Design Spec

**Date:** 2026-04-04
**Status:** Approved
**Scope:** Frontend only (backend SSE events already emitted)

---

## Goal

Display live, meaningful visual feedback whenever an agent is running — across every surface where agents execute — so users always know what the agent is doing, which tools it's using, and what happened after it responds.

---

## Scope

Applies to **all agent execution surfaces**:
- `/forge` — Forge Assistant chat (multi-tab)
- `/agents/[id]` — Agent detail page (run panel)
- `/sandbox` — Sandbox execution page
- `ChatSlideOver` — floating chat slide-over
- Any future surface that calls `consumeSsePath` / `consumeExecutionSse`

---

## SSE Events (already emitted by backend)

The backend (`langgraph_orchestrator.py`) already emits these events on every execution:

| Event type     | Payload fields                        | Meaning                        |
|----------------|---------------------------------------|--------------------------------|
| `agent_start`  | `agent_name`, `node_type`, `input_preview` | A graph node started executing |
| `agent_end`    | `agent_name`, `node_type`, `duration_ms`   | A graph node finished          |
| `tool_call`    | `tool_name`, `args`                   | A tool is being called         |
| `tool_result`  | `tool_name`, `result`                 | Tool returned a result         |
| `token`        | `content`                             | LLM streaming token            |
| `interrupt`    | `execution_id`, `pending_tools`       | HITL pause — needs human input |
| `complete`     | `output`, `cost_usd`, `duration_ms`   | Execution finished             |
| `error`        | `message`                             | Execution failed               |

No backend changes are required for this feature.

---

## Design Decisions

### 1. Animation Style: Floating Toasts

While the agent is running, events surface as **floating toast notifications** that appear near the active message thread. Toasts stack (newest on top) and auto-dismiss when `complete` or `error` is received.

**Why toasts:** Non-intrusive, modern, and consistent with how other AI chat products surface agent activity. Doesn't pollute the message history.

### 2. Persistence: Step Chips Under Each Message

After the agent responds and toasts dismiss, the steps that occurred are preserved as **small chips rendered below the assistant message bubble**:

```
[🔧 web_search · 0.8s]  [📜 summarize]  [✓ 2.1s total]
```

Chips are stored in message metadata (`steps` array on `ChatMessage`). They are permanent — the user can always see what happened for any past message.

### 3. Icon Set

Each event type maps to a unique animated icon:

| Event          | Icon | Color   | Animation              |
|----------------|------|---------|------------------------|
| `agent_start`  | ⚙ SVG spinner | violet `#c084fc` | rotate + waveform bars |
| `tool_call`    | 🔧 wrench SVG | blue `#60a5fa`   | pivot ±18° loop        |
| `skill` (code/instruction node) | 📜 scroll SVG | green `#4ade80` | fade-in static |
| `token` / LLM responding | waveform bars | green `#4ade80` | wave scale Y animation |
| `interrupt`    | custom SVG person+pause | red `#f87171` | pulse ring |
| `complete`     | ✓ checkmark | green `#4ade80` | fade-in |
| `error`        | ✕ | red `#f87171` | shake |

The **waveform icon** (6 vertical bars that animate with `scaleY`) is used for the "generating response" state (active `token` stream). Not an emoji — custom SVG rendered inline.

The **interrupt icon** is a custom SVG: person silhouette with pause bars overlaid + an animated red alert dot. Not a hand emoji.

### 4. Interrupt Popup — Redesigned

The existing `InterruptModal` is replaced with a redesigned popup:

**Visual changes:**
- Animated border glow (`box-shadow` pulse in violet)
- Interrupt icon with pulsing ring at top-left of header
- Per-tool-call card with **3 explicit action buttons**: `✓ Approuver` · `✕ Rejeter` · `✎ Modifier`
- Editable `<textarea>` for the tool argument (enabled only when "Approuver" or "Modifier")
- "Envoyer les décisions →" CTA with gradient purple background + lift on hover

**Behavior (unchanged from existing logic):**
- `decision: "approve" | "reject"` + optional edited `arg`
- Cancel button aborts execution
- `onDecided(decisions[])` callback — same interface as current `InterruptModal`

---

## Component Architecture

### New: `useAgentActivity` hook

```ts
// frontend/src/hooks/useAgentActivity.ts
type AgentStep = {
  event: 'tool_call' | 'skill' | 'agent_start' | 'agent_end' | 'token' | 'complete' | 'error'
  label: string       // human-readable: "web_search", "summarize", "llm_node"
  durationMs?: number
  timestamp: number
}

type AgentActivity = {
  toasts: AgentStep[]        // live, dismissed on complete/error
  steps: AgentStep[]         // accumulates for chip display
  isRunning: boolean
  interrupt: InterruptPayload | null
}
```

Consumes raw SSE events via `onLine` callback. Returns `toasts`, `steps`, `isRunning`, `interrupt`. Replaces ad-hoc SSE parsing scattered across pages.

### New: `AgentToastStack` component

```tsx
// frontend/src/components/agent/AgentToastStack.tsx
```

Renders live toasts during execution. Positioned `absolute` or `sticky` near the bottom of the chat area. Auto-dismisses each toast 400ms after `complete` received (staggered fade-out).

### New: `AgentStepChips` component

```tsx
// frontend/src/components/agent/AgentStepChips.tsx
```

Renders the persistent chips under a message. Receives `steps: AgentStep[]`. No state — pure display.

### New: `AgentActivityIcon` component

```tsx
// frontend/src/components/agent/AgentActivityIcon.tsx
```

Renders the correct animated SVG icon given an `event` type. Used by both `AgentToastStack` and chips. All animations are CSS `@keyframes` — no JS animation library required.

### Modified: `InterruptModal` → `InterruptPopup`

Replace `InterruptModal.tsx` with `InterruptPopup.tsx`:
- Same props interface (`executionId`, `pendingTools`, `onDecided`, `onCancel`)
- New visual design per spec (glow border, 3-button decision UI, person+pause icon)
- "edit" decision type added: sets `decision: "approve"` with modified `arg`

### Modified: `ChatMessage` type

```ts
// frontend/src/types/chat.ts
type ChatMessage = {
  role: "user" | "assistant"
  content: string
  streaming?: boolean
  failed?: boolean
  timestamp: number
  audioB64?: string | null
  steps?: AgentStep[]          // ← new: populated on complete
}
```

### Integration points

Each page/component that currently calls `consumeForgeSse` / `consumeExecutionSse` / `consumeSsePath` adopts `useAgentActivity`:

1. **`/forge/page.tsx`** — replace inline SSE handler with `useAgentActivity`, render `<AgentToastStack>` in the chat panel, attach `steps` to the last assistant message on `complete`
2. **`/sandbox/page.tsx`** — same pattern
3. **`/agents/[id]/page.tsx`** — same pattern
4. **`ChatSlideOver.tsx`** — same pattern

---

## Animation Spec

All animations are pure CSS `@keyframes`, no dependencies:

```css
@keyframes wrench-pivot  { 0%,100%{transform:rotate(0)} 25%{transform:rotate(-18deg)} 75%{transform:rotate(18deg)} }
@keyframes wave-bar      { 0%,100%{transform:scaleY(0.35)} 50%{transform:scaleY(1)} }
@keyframes spin-slow     { to{transform:rotate(360deg)} }
@keyframes pulse-ring    { 0%{transform:scale(1);opacity:.6} 100%{transform:scale(2);opacity:0} }
@keyframes toast-in      { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
@keyframes toast-out     { from{opacity:1;transform:translateY(0)} to{opacity:0;transform:translateY(-6px)} }
@keyframes modal-glow    { 0%,100%{box-shadow:0 0 8px rgba(167,139,250,.3)} 50%{box-shadow:0 0 24px rgba(167,139,250,.7)} }
@keyframes alert-pulse   { 0%,100%{opacity:1} 50%{opacity:.25} }
```

Each bar in the waveform gets a staggered `animation-delay` (0s, 0.1s, 0.2s, 0.3s, 0.15s, 0.05s) for a natural wave effect.

---

## Out of Scope

- No changes to backend SSE events
- No new API endpoints
- No changes to `ExecutionLog` (kept as-is for the raw debug view)
- No animation library (Framer Motion, etc.) — CSS only to keep bundle size minimal
- Long-term memory feature is a separate spec

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `frontend/src/hooks/useAgentActivity.ts` | Create |
| `frontend/src/components/agent/AgentToastStack.tsx` | Create |
| `frontend/src/components/agent/AgentStepChips.tsx` | Create |
| `frontend/src/components/agent/AgentActivityIcon.tsx` | Create |
| `frontend/src/components/execution/InterruptPopup.tsx` | Create (replaces InterruptModal) |
| `frontend/src/types/chat.ts` | Modify (add `steps` field) |
| `frontend/src/app/forge/page.tsx` | Modify (integrate hook + components) |
| `frontend/src/app/sandbox/page.tsx` | Modify |
| `frontend/src/app/agents/[id]/page.tsx` | Modify |
| `frontend/src/components/chat/ChatSlideOver.tsx` | Modify |
