# Agent Real-Time Animations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display live animated toasts while an agent executes, then persist step chips under each assistant message — across all execution surfaces (Forge, ChatSlideOver, Agents page).

**Architecture:** New `useAgentActivity` hook centralises SSE event parsing and exposes `toasts`, `steps`, `isRunning`, `interrupt`. Three pure display components (`AgentActivityIcon`, `AgentToastStack`, `AgentStepChips`) consume the hook output. `InterruptModal` is replaced by `InterruptPopup` with approve/reject/edit per tool. All integration points (`forge/page.tsx`, `ChatSlideOver.tsx`, `agents/[id]/page.tsx`) adopt the hook and render the new components.

**Tech Stack:** Next.js 15 / React 19, TypeScript, Tailwind CSS, CSS `@keyframes` only (no animation library), existing SSE utility (`lib/sse.ts`).

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/src/types/chat.ts` | Modify | Add `steps` field + `AgentStep` type |
| `frontend/src/hooks/useAgentActivity.ts` | Create | Parse SSE events → toasts / steps / interrupt state |
| `frontend/src/components/agent/AgentActivityIcon.tsx` | Create | Animated SVG icon per event type |
| `frontend/src/components/agent/AgentToastStack.tsx` | Create | Live floating toasts during execution |
| `frontend/src/components/agent/AgentStepChips.tsx` | Create | Persistent chips under a message |
| `frontend/src/components/execution/InterruptPopup.tsx` | Create | Redesigned HITL modal (approve/reject/edit) |
| `frontend/src/app/forge/page.tsx` | Modify | Adopt hook, render toasts + chips |
| `frontend/src/components/chat/ChatSlideOver.tsx` | Modify | Adopt hook, render toasts + chips |
| `frontend/src/app/agents/[id]/page.tsx` | Modify | Adopt hook, render toasts if run panel exists |

---

## Task 1: Extend `ChatMessage` type with `AgentStep`

**Files:**
- Modify: `frontend/src/types/chat.ts`

- [ ] **Step 1: Replace file contents**

```typescript
// frontend/src/types/chat.ts

export type AgentStep = {
  event: "tool_call" | "tool_result" | "skill" | "agent_start" | "agent_end" | "complete" | "error";
  label: string;       // human-readable: "web_search", "summarize", "llm_node"
  durationMs?: number;
  timestamp: number;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  failed?: boolean;
  timestamp: number;
  audioB64?: string | null;
  steps?: AgentStep[];  // populated when execution completes
};
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && rtk npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors related to `chat.ts`.

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/types/chat.ts
rtk git commit -m "feat(animations): add AgentStep type to ChatMessage"
```

---

## Task 2: Create `useAgentActivity` hook

**Files:**
- Create: `frontend/src/hooks/useAgentActivity.ts`

- [ ] **Step 1: Create the hook**

```typescript
// frontend/src/hooks/useAgentActivity.ts
"use client";

import { useCallback, useRef, useState } from "react";
import { AgentStep } from "@/types/chat";

export type InterruptPayload = {
  execution_id: string;
  pending_tools: { tool_name: string; arg: string }[];
};

export type AgentActivity = {
  toasts: AgentStep[];
  steps: AgentStep[];
  isRunning: boolean;
  interrupt: InterruptPayload | null;
};

/**
 * Parses raw SSE events from any agent execution stream and maintains
 * live toast state + accumulated step history.
 *
 * Usage:
 *   const { activity, onLine, reset } = useAgentActivity();
 *   // Pass `onLine` as the callback to consumeForgeSse / consumeExecutionSse
 *   // Read `activity.toasts` for live display, `activity.steps` for chips
 */
export function useAgentActivity() {
  const [activity, setActivity] = useState<AgentActivity>({
    toasts: [],
    steps: [],
    isRunning: false,
    interrupt: null,
  });

  const startTimeRef = useRef<number>(Date.now());

  const reset = useCallback(() => {
    startTimeRef.current = Date.now();
    setActivity({ toasts: [], steps: [], isRunning: false, interrupt: null });
  }, []);

  const onLine = useCallback((eventName: string, dataJson: string) => {
    let data: Record<string, unknown> = {};
    try { data = JSON.parse(dataJson); } catch { /* ignore */ }

    const now = Date.now();

    switch (eventName) {
      case "agent_start": {
        const label = (data.agent_name as string) ?? (data.node_type as string) ?? "agent";
        const step: AgentStep = { event: "agent_start", label, timestamp: now };
        setActivity((prev) => ({
          ...prev,
          isRunning: true,
          toasts: [...prev.toasts, step],
          steps: [...prev.steps, step],
        }));
        break;
      }
      case "tool_call": {
        const label = (data.tool_name as string) ?? "tool";
        const step: AgentStep = { event: "tool_call", label, timestamp: now };
        setActivity((prev) => ({
          ...prev,
          toasts: [...prev.toasts, step],
          steps: [...prev.steps, step],
        }));
        break;
      }
      case "tool_result": {
        const label = (data.tool_name as string) ?? "tool";
        // Update matching tool_call step with duration, don't add a new toast
        setActivity((prev) => {
          const callStep = [...prev.steps].reverse().find(
            (s) => s.event === "tool_call" && s.label === label
          );
          const durationMs = callStep ? now - callStep.timestamp : undefined;
          const updatedSteps = prev.steps.map((s) =>
            s === callStep ? { ...s, durationMs } : s
          );
          return { ...prev, steps: updatedSteps };
        });
        break;
      }
      case "interrupt": {
        const payload: InterruptPayload = {
          execution_id: (data.execution_id as string) ?? "",
          pending_tools: (data.pending_tools as InterruptPayload["pending_tools"]) ?? [],
        };
        setActivity((prev) => ({ ...prev, interrupt: payload }));
        break;
      }
      case "complete":
      case "done":
      case "completed": {
        const durationMs = now - startTimeRef.current;
        const doneStep: AgentStep = { event: "complete", label: "done", durationMs, timestamp: now };
        // Dismiss toasts after a short delay (handled in AgentToastStack via isRunning=false)
        setActivity((prev) => ({
          ...prev,
          isRunning: false,
          interrupt: null,
          steps: [...prev.steps, doneStep],
          toasts: [], // clear live toasts
        }));
        break;
      }
      case "error": {
        const errStep: AgentStep = { event: "error", label: "error", timestamp: now };
        setActivity((prev) => ({
          ...prev,
          isRunning: false,
          toasts: [],
          steps: [...prev.steps, errStep],
        }));
        break;
      }
      default:
        break;
    }
  }, []);

  return { activity, onLine, reset };
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && rtk npx tsc --noEmit 2>&1 | head -20
```

Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/hooks/useAgentActivity.ts
rtk git commit -m "feat(animations): add useAgentActivity hook"
```

---

## Task 3: Create `AgentActivityIcon` component

**Files:**
- Create: `frontend/src/components/agent/AgentActivityIcon.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/agent/AgentActivityIcon.tsx
"use client";

import { AgentStep } from "@/types/chat";

type Props = {
  event: AgentStep["event"] | "agent_start";
  size?: number;
};

/**
 * Renders an animated SVG icon for a given agent event type.
 * All animations are pure CSS @keyframes — no JS animation library.
 */
export function AgentActivityIcon({ event, size = 28 }: Props) {
  const s = size;
  const r = Math.round(s * 0.32); // border-radius

  const wrap = (bg: string, content: React.ReactNode) => (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: s,
        height: s,
        borderRadius: r,
        background: bg,
        flexShrink: 0,
      }}
    >
      {content}
    </span>
  );

  if (event === "agent_start") {
    return wrap(
      "#2d1f3d",
      <>
        <style>{`
          @keyframes af-spin { to { transform: rotate(360deg); } }
        `}</style>
        <svg width={s * 0.55} height={s * 0.55} viewBox="0 0 20 20" fill="none">
          <circle cx="10" cy="10" r="8" stroke="#c084fc" strokeWidth="2" strokeDasharray="28 8"
            style={{ animation: "af-spin 1.5s linear infinite", transformOrigin: "center" }} />
        </svg>
      </>
    );
  }

  if (event === "tool_call") {
    return wrap(
      "#1e3a5f",
      <>
        <style>{`
          @keyframes af-wrench {
            0%,100% { transform: rotate(0deg); }
            25%      { transform: rotate(-18deg); }
            75%      { transform: rotate(18deg); }
          }
        `}</style>
        <svg width={s * 0.55} height={s * 0.55} viewBox="0 0 20 20" fill="none"
          style={{ animation: "af-wrench 0.7s ease-in-out infinite" }}>
          <path d="M12.5 2a5.5 5.5 0 0 0-5.18 7.37L2 14.75 3.25 16l5.38-5.32A5.5 5.5 0 1 0 12.5 2zm0 9a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z"
            fill="#60a5fa" />
        </svg>
      </>
    );
  }

  if (event === "skill") {
    return wrap(
      "#1a3320",
      <svg width={s * 0.55} height={s * 0.55} viewBox="0 0 20 20" fill="none">
        <rect x="3" y="2" width="14" height="16" rx="2" stroke="#4ade80" strokeWidth="1.8" fill="none" />
        <line x1="6" y1="7" x2="14" y2="7" stroke="#4ade80" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="6" y1="10" x2="14" y2="10" stroke="#4ade80" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="6" y1="13" x2="11" y2="13" stroke="#4ade80" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }

  if (event === "complete") {
    return wrap(
      "#0f2d1f",
      <>
        <style>{`
          @keyframes af-fadein { from { opacity: 0; transform: scale(0.7); } to { opacity: 1; transform: scale(1); } }
        `}</style>
        <svg width={s * 0.55} height={s * 0.55} viewBox="0 0 20 20" fill="none"
          style={{ animation: "af-fadein 0.3s ease" }}>
          <path d="M4 10l5 5 7-8" stroke="#4ade80" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </>
    );
  }

  if (event === "error") {
    return wrap(
      "#2d1010",
      <>
        <style>{`
          @keyframes af-shake {
            0%,100% { transform: translateX(0); }
            20%      { transform: translateX(-3px); }
            60%      { transform: translateX(3px); }
          }
        `}</style>
        <svg width={s * 0.55} height={s * 0.55} viewBox="0 0 20 20" fill="none"
          style={{ animation: "af-shake 0.4s ease" }}>
          <path d="M10 4v7M10 14v1" stroke="#f87171" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
      </>
    );
  }

  // interrupt — person + pause + alert ring
  return wrap(
    "#2d1020",
    <>
      <style>{`
        @keyframes af-pulse-ring {
          0%   { transform: scale(1); opacity: 0.7; }
          100% { transform: scale(2.2); opacity: 0; }
        }
        @keyframes af-alert { 0%,100%{opacity:1} 50%{opacity:.25} }
      `}</style>
      <span style={{ position: "relative", display: "inline-flex", alignItems: "center", justifyContent: "center", width: s * 0.7, height: s * 0.7 }}>
        <span style={{
          position: "absolute", inset: -2, borderRadius: "50%",
          border: "1.5px solid #f87171",
          animation: "af-pulse-ring 1.4s ease-out infinite",
        }} />
        <svg width={s * 0.6} height={s * 0.6} viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="6" r="3.5" fill="#c084fc" />
          <path d="M5 20c0-3.866 3.134-7 7-7s7 3.134 7 7" stroke="#c084fc" strokeWidth="1.8" strokeLinecap="round" fill="none" />
          <rect x="8.5" y="9" width="2.5" height="8" rx="1.2" fill="#2d1020" />
          <rect x="13" y="9" width="2.5" height="8" rx="1.2" fill="#2d1020" />
          <circle cx="19" cy="5" r="3" fill="#f87171" style={{ animation: "af-alert 0.9s infinite" }} />
          <text x="19" y="7.5" textAnchor="middle" fontSize="4.5" fill="white" fontWeight="bold">!</text>
        </svg>
      </span>
    </>
  );
}

/** Waveform bars: used for "generating response" (token stream active) */
export function WaveformIcon({ color = "#4ade80", height = 20 }: { color?: string; height?: number }) {
  const bars = [0.4, 0.75, 1, 0.85, 0.6, 0.45];
  return (
    <>
      <style>{`
        @keyframes af-wave {
          0%,100% { transform: scaleY(0.35); }
          50%      { transform: scaleY(1); }
        }
      `}</style>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 2, height }}>
        {bars.map((h, i) => (
          <span key={i} style={{
            width: 3,
            height: height * h,
            borderRadius: 2,
            background: color,
            display: "block",
            animation: `af-wave 1s ${i * 0.1}s ease-in-out infinite`,
            transformOrigin: "bottom",
          }} />
        ))}
      </span>
    </>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && rtk npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/components/agent/AgentActivityIcon.tsx
rtk git commit -m "feat(animations): add AgentActivityIcon and WaveformIcon components"
```

---

## Task 4: Create `AgentToastStack` component

**Files:**
- Create: `frontend/src/components/agent/AgentToastStack.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/agent/AgentToastStack.tsx
"use client";

import { AgentStep } from "@/types/chat";
import { AgentActivityIcon, WaveformIcon } from "./AgentActivityIcon";

type Props = {
  toasts: AgentStep[];
  isRunning: boolean;
};

function toastLabel(step: AgentStep): string {
  if (step.event === "agent_start") return `réfléchit · ${step.label}`;
  if (step.event === "tool_call")   return step.label;
  if (step.event === "complete")    return "réponse générée";
  if (step.event === "error")       return "erreur";
  if (step.event === "interrupt")   return "en attente d'approbation";
  return step.label;
}

/**
 * Renders up to 3 live toasts stacked, newest on top.
 * Toasts auto-clear when `isRunning` becomes false (handled by useAgentActivity).
 * Positioned as a block element — the parent positions it where needed.
 */
export function AgentToastStack({ toasts, isRunning }: Props) {
  // Show last 3 toasts; add a "generating" toast when streaming tokens
  const visible = toasts.slice(-3);

  if (!isRunning && visible.length === 0) return null;

  return (
    <>
      <style>{`
        @keyframes af-toast-in {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 8 }}>
        {isRunning && (
          <div className="af-toast-live" style={{
            display: "flex", alignItems: "center", gap: 10,
            background: "#1e1e2e", border: "1px solid #3d3d5e",
            borderRadius: 10, padding: "9px 14px",
            fontSize: 13, color: "#e2e8f0",
            animation: "af-toast-in 0.3s ease",
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: 9,
              background: "#1a2a1a",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <WaveformIcon />
            </div>
            <div>
              <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 2 }}>rédige la réponse</div>
              <div style={{ fontSize: 12, color: "#4ade80" }}>génération en cours…</div>
            </div>
          </div>
        )}
        {[...visible].reverse().map((step, idx) => (
          <div key={`${step.timestamp}-${idx}`} style={{
            display: "flex", alignItems: "center", gap: 10,
            background: "#1e1e2e",
            border: "1px solid #3d3d5e",
            borderRadius: 10, padding: "9px 14px",
            fontSize: 13, color: "#e2e8f0",
            opacity: 1 - idx * 0.25,
            transform: `scale(${1 - idx * 0.03})`,
            transformOrigin: "top center",
            animation: idx === 0 ? "af-toast-in 0.3s ease" : undefined,
            transition: "opacity 0.2s, transform 0.2s",
          }}>
            <AgentActivityIcon event={step.event} size={32} />
            <div>
              <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 2 }}>
                {step.event.replace("_", " ")}
              </div>
              <div>{toastLabel(step)}</div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && rtk npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/components/agent/AgentToastStack.tsx
rtk git commit -m "feat(animations): add AgentToastStack component"
```

---

## Task 5: Create `AgentStepChips` component

**Files:**
- Create: `frontend/src/components/agent/AgentStepChips.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/agent/AgentStepChips.tsx
"use client";

import { AgentStep } from "@/types/chat";

type Props = {
  steps: AgentStep[];
};

const EVENT_ICONS: Record<AgentStep["event"], string> = {
  tool_call:   "🔧",
  tool_result: "🔧",
  skill:       "📜",
  agent_start: "⚙",
  agent_end:   "⚙",
  complete:    "✓",
  error:       "✕",
};

const CHIP_COLORS: Record<AgentStep["event"], { bg: string; border: string; color: string }> = {
  tool_call:   { bg: "#0d1a2e", border: "#1e3a5f", color: "#60a5fa" },
  tool_result: { bg: "#0d1a2e", border: "#1e3a5f", color: "#60a5fa" },
  skill:       { bg: "#0d1a0d", border: "#1a3320", color: "#4ade80" },
  agent_start: { bg: "#1a0d2e", border: "#2d1f3d", color: "#c084fc" },
  agent_end:   { bg: "#1a0d2e", border: "#2d1f3d", color: "#c084fc" },
  complete:    { bg: "#0a1a0a", border: "#14532d", color: "#4ade80" },
  error:       { bg: "#1a0a0a", border: "#431407", color: "#f87171" },
};

/**
 * Renders compact step chips below an assistant message.
 * Only shows meaningful steps (tool_call, skill, complete, error).
 * Filters out agent_start/agent_end noise for cleaner display.
 */
export function AgentStepChips({ steps }: Props) {
  const visible = steps.filter((s) =>
    s.event === "tool_call" || s.event === "skill" || s.event === "complete" || s.event === "error"
  );

  if (visible.length === 0) return null;

  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
      {visible.map((step, i) => {
        const c = CHIP_COLORS[step.event];
        const icon = EVENT_ICONS[step.event];
        const label = step.event === "complete"
          ? step.durationMs ? `✓ ${(step.durationMs / 1000).toFixed(1)}s` : "✓ done"
          : `${icon} ${step.label}${step.durationMs ? ` · ${(step.durationMs / 1000).toFixed(1)}s` : ""}`;

        return (
          <span key={i} style={{
            display: "inline-flex", alignItems: "center", gap: 4,
            background: c.bg, border: `1px solid ${c.border}`,
            borderRadius: 6, padding: "3px 8px",
            fontSize: 10, fontWeight: 600, color: c.color,
            letterSpacing: "0.02em",
          }}>
            {label}
          </span>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && rtk npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/components/agent/AgentStepChips.tsx
rtk git commit -m "feat(animations): add AgentStepChips component"
```

---

## Task 6: Create `InterruptPopup` (replaces `InterruptModal`)

**Files:**
- Create: `frontend/src/components/execution/InterruptPopup.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/execution/InterruptPopup.tsx
"use client";

import { useState } from "react";
import { AgentActivityIcon } from "@/components/agent/AgentActivityIcon";

type PendingTool = {
  tool_name: string;
  arg: string;
};

type Decision = {
  tool_name: string;
  decision: "approve" | "reject";
  arg?: string;
};

type Props = {
  executionId: string;
  pendingTools: PendingTool[];
  onDecided: (decisions: Decision[]) => void;
  onCancel: () => void;
};

/**
 * Redesigned HITL interrupt popup.
 * Same props interface as InterruptModal — drop-in replacement.
 * Adds "edit" mode: approve with a modified argument.
 */
export function InterruptPopup({ executionId, pendingTools, onDecided, onCancel }: Props) {
  const [decisions, setDecisions] = useState<Record<string, Decision>>(
    Object.fromEntries(
      pendingTools.map((t) => [t.tool_name, { tool_name: t.tool_name, decision: "approve", arg: t.arg }])
    )
  );

  function setDecision(toolName: string, field: keyof Decision, value: string) {
    setDecisions((prev) => ({ ...prev, [toolName]: { ...prev[toolName], [field]: value } }));
  }

  return (
    <>
      <style>{`
        @keyframes af-modal-glow {
          0%,100% { box-shadow: 0 0 8px rgba(167,139,250,.25), 0 20px 60px rgba(0,0,0,.6); }
          50%     { box-shadow: 0 0 24px rgba(167,139,250,.55), 0 20px 60px rgba(0,0,0,.6); }
        }
        @keyframes af-slide-up {
          from { opacity: 0; transform: translateY(20px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      <div style={{
        position: "fixed", inset: 0, zIndex: 50,
        display: "flex", alignItems: "center", justifyContent: "center",
        background: "rgba(0,0,0,0.65)", backdropFilter: "blur(4px)",
      }}>
        <div style={{
          width: "100%", maxWidth: 480, margin: "0 16px",
          background: "#0d0d1a",
          border: "1px solid rgba(167,139,250,0.4)",
          borderRadius: 16, padding: 24,
          animation: "af-slide-up 0.4s ease, af-modal-glow 2s ease-in-out infinite",
        }}>
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
            <AgentActivityIcon event="interrupt" size={40} />
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: "#fff" }}>
                Approbation humaine requise
              </div>
              <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 2 }}>
                Exécution en pause ·{" "}
                <span style={{ fontFamily: "monospace", fontSize: 11, color: "#a78bfa" }}>
                  {executionId.slice(0, 8)}…
                </span>
              </div>
            </div>
          </div>

          {/* Tool cards */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {pendingTools.map((tool, idx) => {
              const d = decisions[tool.tool_name];
              return (
                <div key={tool.tool_name} style={{
                  background: "#111827", border: "1px solid #1f2937",
                  borderRadius: 10, padding: 16,
                }}>
                  <div style={{
                    fontFamily: "monospace", fontSize: 13, fontWeight: 700,
                    color: "#c084fc", marginBottom: 12,
                    display: "flex", alignItems: "center", gap: 8,
                  }}>
                    🔧 {tool.tool_name}
                    <span style={{ marginLeft: "auto", fontFamily: "sans-serif", fontSize: 10, color: "#64748b", fontWeight: 400 }}>
                      call #{idx + 1}
                    </span>
                  </div>

                  {/* Decision buttons */}
                  <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
                    {(["approve", "reject"] as const).map((dec) => {
                      const isActive = d?.decision === dec;
                      const styles = dec === "approve"
                        ? { bg: isActive ? "#166534" : "#14532d", color: "#4ade80", border: "#166534" }
                        : { bg: isActive ? "#7f1d1d" : "#2d1515", color: "#f87171", border: "#7f1d1d" };
                      return (
                        <button key={dec} type="button"
                          onClick={() => setDecision(tool.tool_name, "decision", dec)}
                          style={{
                            flex: 1, padding: "8px 0", borderRadius: 8,
                            fontSize: 12, fontWeight: 600,
                            background: styles.bg, color: styles.color,
                            border: `1px solid ${styles.border}`,
                            cursor: "pointer",
                            boxShadow: isActive && dec === "approve" ? "0 0 12px rgba(74,222,128,.3)" : undefined,
                          }}>
                          {dec === "approve" ? "✓ Approuver" : "✕ Rejeter"}
                        </button>
                      );
                    })}
                    <button type="button"
                      onClick={() => {
                        setDecision(tool.tool_name, "decision", "approve");
                        // Focus the textarea to signal edit mode
                        document.getElementById(`arg-${tool.tool_name}`)?.focus();
                      }}
                      style={{
                        flex: 1, padding: "8px 0", borderRadius: 8,
                        fontSize: 12, fontWeight: 600,
                        background: "#1e1e2e", color: "#a78bfa",
                        border: "1px solid #3d3d5e",
                        cursor: "pointer",
                      }}>
                      ✎ Modifier
                    </button>
                  </div>

                  {/* Argument textarea */}
                  <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase", color: "#64748b", marginBottom: 6 }}>
                    Argument
                  </div>
                  <textarea
                    id={`arg-${tool.tool_name}`}
                    value={d?.arg ?? ""}
                    onChange={(e) => setDecision(tool.tool_name, "arg", e.target.value)}
                    disabled={d?.decision === "reject"}
                    rows={2}
                    style={{
                      width: "100%", background: "#0d0d1a",
                      border: "1px solid #2d2d4e", borderRadius: 6,
                      padding: "8px 10px", fontFamily: "monospace",
                      fontSize: 11, color: "#94a3b8", resize: "none",
                      outline: "none", boxSizing: "border-box",
                      opacity: d?.decision === "reject" ? 0.4 : 1,
                    }}
                  />
                </div>
              );
            })}
          </div>

          {/* Footer actions */}
          <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
            <button type="button" onClick={onCancel} style={{
              flex: 1, padding: "10px 0", borderRadius: 8, fontSize: 13,
              background: "transparent", color: "#64748b",
              border: "1px solid #1f2937", cursor: "pointer",
            }}>
              Annuler l&apos;exécution
            </button>
            <button type="button" onClick={() => onDecided(Object.values(decisions))} style={{
              flex: 2, padding: "10px 0", borderRadius: 8, fontSize: 13, fontWeight: 700,
              background: "linear-gradient(135deg, #7c3aed, #a78bfa)",
              color: "#fff", border: "none", cursor: "pointer",
            }}>
              Envoyer les décisions →
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && rtk npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/components/execution/InterruptPopup.tsx
rtk git commit -m "feat(animations): add InterruptPopup component"
```

---

## Task 7: Integrate into `forge/page.tsx`

**Files:**
- Modify: `frontend/src/app/forge/page.tsx`

The changes are surgical — we add the hook, pipe `onLine` into the SSE handler, render toasts above the input, and attach `steps` to the last message on complete.

- [ ] **Step 1: Add imports at top of file**

Find the existing imports block and add:

```typescript
import { useAgentActivity } from "@/hooks/useAgentActivity";
import { AgentToastStack } from "@/components/agent/AgentToastStack";
import { AgentStepChips } from "@/components/agent/AgentStepChips";
import { InterruptPopup } from "@/components/execution/InterruptPopup";
```

- [ ] **Step 2: Add per-tab activity state**

In `TabState` type, add:
```typescript
type TabState = {
  convId: string;
  messages: ChatMessage[];
  provider: string;
  model: string;
  draft: string;
  loading: boolean;
  error: string | null;
  // steps accumulated for current/last execution — keyed by message index
  lastSteps: import("@/types/chat").AgentStep[];
};
```

In `makeTab`, add `lastSteps: []`.

- [ ] **Step 3: Add `useAgentActivity` hook call**

Inside `ForgePage()`, after the existing `useState` calls:

```typescript
const { activity, onLine: activityOnLine, reset: resetActivity } = useAgentActivity();
```

- [ ] **Step 4: Wire `activityOnLine` into the SSE handler**

In `handleSend`, find the `consumeForgeSse` call and add `activityOnLine` alongside the existing handler:

```typescript
// Before consumeForgeSse call
resetActivity();

await consumeForgeSse(
  exec.execution_id,
  (event, dataJson) => {
    activityOnLine(event, dataJson);   // ← add this line
    if (event === "token") {
      // ... existing token handling unchanged ...
```

- [ ] **Step 5: Attach steps to last message on complete**

In the finalize block after `consumeForgeSse` resolves, attach the accumulated steps:

```typescript
setTabs((prev) =>
  prev.map((t) => {
    if (t.convId !== convId) return t;
    const msgs = t.messages.map((m, i) =>
      i === t.messages.length - 1
        ? { ...m, streaming: false, failed: !accumulated, content: accumulated || m.content, steps: activity.steps }
        : m,
    );
    return { ...t, messages: msgs, loading: false, lastSteps: [] };
  }),
);
```

- [ ] **Step 6: Render `AgentToastStack` above the input area**

Find the input textarea in the JSX and add above it:

```tsx
<AgentToastStack toasts={activity.toasts} isRunning={activity.isRunning} />
```

- [ ] **Step 7: Render `AgentStepChips` under each assistant message**

In the messages render loop, find where assistant messages are rendered and add after the message content:

```tsx
{msg.role === "assistant" && msg.steps && msg.steps.length > 0 && (
  <AgentStepChips steps={msg.steps} />
)}
```

- [ ] **Step 8: Render `InterruptPopup` when interrupt fires**

Add at the bottom of the JSX (before closing `</ToolShell>`):

```tsx
{activity.interrupt && (
  <InterruptPopup
    executionId={activity.interrupt.execution_id}
    pendingTools={activity.interrupt.pending_tools}
    onDecided={async (decisions) => {
      // POST decisions to the existing HITL endpoint
      await api(`/api/v1/executions/${activity.interrupt!.execution_id}/hitl`, {
        method: "POST",
        body: JSON.stringify({ decisions }),
      });
    }}
    onCancel={() => {
      abortRefs.current[activeTabId ?? ""]?.abort();
    }}
  />
)}
```

- [ ] **Step 9: Verify TypeScript and build**

```bash
cd frontend && rtk npx tsc --noEmit 2>&1 | head -30
```

- [ ] **Step 10: Commit**

```bash
rtk git add frontend/src/app/forge/page.tsx
rtk git commit -m "feat(animations): integrate agent activity animations into Forge"
```

---

## Task 8: Integrate into `ChatSlideOver.tsx`

**Files:**
- Modify: `frontend/src/components/chat/ChatSlideOver.tsx`

Same pattern as Task 7 but simpler (single conversation, no tabs).

- [ ] **Step 1: Add imports**

```typescript
import { useAgentActivity } from "@/hooks/useAgentActivity";
import { AgentToastStack } from "@/components/agent/AgentToastStack";
import { AgentStepChips } from "@/components/agent/AgentStepChips";
```

- [ ] **Step 2: Instantiate the hook inside `ChatSlideOver`**

```typescript
const { activity, onLine: activityOnLine, reset: resetActivity } = useAgentActivity();
```

- [ ] **Step 3: Find the SSE handler in `ChatSlideOver` and wire `activityOnLine`**

Locate the `consumeExecutionSse` (or `consumeSsePath`) call. Before it, call `resetActivity()`. Inside the callback, add `activityOnLine(event, dataJson)` as the first line.

- [ ] **Step 4: Attach steps to last message on complete**

After the SSE completes, update the last assistant message to include `steps: activity.steps`.

- [ ] **Step 5: Render `AgentToastStack` above input**

```tsx
<AgentToastStack toasts={activity.toasts} isRunning={activity.isRunning} />
```

- [ ] **Step 6: Render `AgentStepChips` under assistant messages**

```tsx
{msg.role === "assistant" && msg.steps && msg.steps.length > 0 && (
  <AgentStepChips steps={msg.steps} />
)}
```

- [ ] **Step 7: Verify TypeScript**

```bash
cd frontend && rtk npx tsc --noEmit 2>&1 | head -30
```

- [ ] **Step 8: Commit**

```bash
rtk git add frontend/src/components/chat/ChatSlideOver.tsx
rtk git commit -m "feat(animations): integrate agent activity animations into ChatSlideOver"
```

---

## Task 9: Final build check and cleanup

- [ ] **Step 1: Full Next.js build**

```bash
cd frontend && rtk npm run build 2>&1 | tail -30
```

Expected: `✓ Compiled successfully` with no type errors.

- [ ] **Step 2: Check `InterruptModal` is no longer imported anywhere**

```bash
rtk grep -r "InterruptModal" frontend/src --include="*.tsx" --include="*.ts"
```

If any results remain (other than the old file), update those imports to use `InterruptPopup`.

- [ ] **Step 3: Add `.superpowers/` to `.gitignore` if not present**

```bash
grep -q "\.superpowers" .gitignore || echo ".superpowers/" >> .gitignore
rtk git add .gitignore
rtk git commit -m "chore: ignore .superpowers brainstorm directory"
```

- [ ] **Step 4: Final commit**

```bash
rtk git add -A
rtk git commit -m "feat(animations): complete real-time agent activity animations"
```
