# HITL Interrupt Modal — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When an agent execution is paused on a tool interrupt, show a modal UI in the agent detail page so the user can approve, reject, or edit the tool call and resume the execution.

**Architecture:** The SSE stream already sends an `interrupt` event with `{"interrupt_state": {"pending_tools": [{"tool_name": "...", "arg": "..."}]}}` when execution pauses. The `run()` function in `frontend/src/app/agents/[id]/page.tsx` receives these via `consumeExecutionSse`. We detect the `interrupt` event inside the SSE callback, set `interruptState`, and show `InterruptModal`. On confirm, POST decisions to `POST /api/v1/agents/{id}/executions/{exec_id}/interrupt` then re-open the SSE stream to watch for completion.

**Tech Stack:** React, Next.js App Router (client component), existing `api()` helper from `@/lib/api`, existing `consumeExecutionSse` from `@/lib/sse`.

---

### Task 1: Create the InterruptModal component

**Files:**
- Create: `frontend/src/components/execution/InterruptModal.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/execution/InterruptModal.tsx
"use client";

import { useState } from "react";

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

export function InterruptModal({ executionId, pendingTools, onDecided, onCancel }: Props) {
  const [decisions, setDecisions] = useState<Record<string, Decision>>(
    Object.fromEntries(
      pendingTools.map((t) => [
        t.tool_name,
        { tool_name: t.tool_name, decision: "approve", arg: t.arg },
      ]),
    ),
  );

  function setDecision(toolName: string, field: keyof Decision, value: string) {
    setDecisions((prev) => ({
      ...prev,
      [toolName]: { ...prev[toolName], [field]: value },
    }));
  }

  function confirm() {
    onDecided(Object.values(decisions));
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-lg rounded-xl border border-af-border/40 bg-af-surface-low p-6 shadow-2xl">
        <h2 className="mb-1 text-lg font-semibold text-white">Human approval required</h2>
        <p className="mb-4 text-sm text-af-muted">
          Execution{" "}
          <span className="font-mono text-xs text-af-muted-dim">
            {executionId.slice(0, 8)}…
          </span>{" "}
          is paused. Review and approve or reject each tool call.
        </p>

        <div className="space-y-4">
          {pendingTools.map((tool) => {
            const d = decisions[tool.tool_name];
            return (
              <div
                key={tool.tool_name}
                className="rounded-lg border border-af-border/30 bg-af-surface p-4"
              >
                <div className="mb-2 flex items-center justify-between">
                  <span className="font-mono text-sm font-medium text-af-primary">
                    {tool.tool_name}
                  </span>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setDecision(tool.tool_name, "decision", "approve")}
                      className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                        d?.decision === "approve"
                          ? "bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-400/50"
                          : "bg-af-surface-low text-af-muted hover:text-white"
                      }`}
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => setDecision(tool.tool_name, "decision", "reject")}
                      className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                        d?.decision === "reject"
                          ? "bg-red-500/20 text-red-400 ring-1 ring-red-400/50"
                          : "bg-af-surface-low text-af-muted hover:text-white"
                      }`}
                    >
                      Reject
                    </button>
                  </div>
                </div>
                <label className="mb-1 block text-xs text-af-muted">Input argument</label>
                <textarea
                  value={d?.arg ?? ""}
                  onChange={(e) => setDecision(tool.tool_name, "arg", e.target.value)}
                  disabled={d?.decision === "reject"}
                  rows={2}
                  className="w-full rounded border border-af-border/30 bg-af-surface-low px-3 py-2 font-mono text-xs text-white placeholder-af-muted-dim outline-none focus:border-af-primary/50 disabled:opacity-40"
                />
              </div>
            );
          })}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-af-border/30 px-4 py-2 text-sm text-af-muted hover:text-white"
          >
            Cancel execution
          </button>
          <button
            type="button"
            onClick={confirm}
            className="rounded-lg bg-af-primary px-4 py-2 text-sm font-medium text-white hover:bg-af-primary/80"
          >
            Submit decisions
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd frontend && git add src/components/execution/InterruptModal.tsx
git commit -m "feat(ui): add InterruptModal component for HITL tool approval"
```

---

### Task 2: Wire InterruptModal into the agent detail page

**Files:**
- Modify: `frontend/src/app/agents/[id]/page.tsx`

The key integration points:
1. Add state for `interruptState` and `interruptExecutionId`
2. In the `run()` SSE callback, detect `interrupt` events and set state
3. When SSE stream ends with `status === "paused"`, the modal stays open
4. On `onDecided`, POST decisions and re-open SSE stream

- [ ] **Step 1: Add InterruptModal import and state to the page**

At the top of `page.tsx`, add the import:

```tsx
import { InterruptModal } from "@/components/execution/InterruptModal";
```

Inside `AgentDetailPage()`, after the existing `useState` declarations (after `const abortRef = useRef...`), add:

```tsx
type PendingTool = { tool_name: string; arg: string };
const [interruptState, setInterruptState] = useState<{
  executionId: string;
  pendingTools: PendingTool[];
} | null>(null);
```

- [ ] **Step 2: Detect interrupt events in the run() SSE callback**

In the `run()` function, the `consumeExecutionSse` call currently passes a callback `(event, dataJson) => { ... }`. Modify that callback to also handle `interrupt` events:

Find this block in `run()`:

```tsx
await consumeExecutionSse(
  id,
  ex.id,
  (event, dataJson) => {
    lines.push({ event, data: dataJson, at: Date.now() });
    setStreamLines([...lines]);
  },
  signal,
);
```

Replace with:

```tsx
await consumeExecutionSse(
  id,
  ex.id,
  (event, dataJson) => {
    lines.push({ event, data: dataJson, at: Date.now() });
    setStreamLines([...lines]);
    if (event === "interrupt") {
      try {
        const parsed = JSON.parse(dataJson);
        const pending: PendingTool[] = parsed?.interrupt_state?.pending_tools ?? [];
        if (pending.length > 0) {
          setInterruptState({ executionId: ex.id, pendingTools: pending });
        }
      } catch {
        /* ignore parse errors */
      }
    }
  },
  signal,
);
```

- [ ] **Step 3: Add the handleInterruptDecision function**

After the `run()` function, add:

```tsx
async function handleInterruptDecision(
  decisions: { tool_name: string; decision: "approve" | "reject"; arg?: string }[],
) {
  if (!interruptState) return;
  const { executionId } = interruptState;
  setInterruptState(null);
  setBusy(true);
  setError(null);
  try {
    await api(`/api/v1/agents/${id}/executions/${executionId}/interrupt`, {
      method: "POST",
      body: JSON.stringify({ decisions }),
    });
    // Re-open SSE stream to watch resumed execution
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    const signal = abortRef.current.signal;
    const lines: LogLine[] = [...streamLines];
    await consumeExecutionSse(
      id,
      executionId,
      (event, dataJson) => {
        lines.push({ event, data: dataJson, at: Date.now() });
        setStreamLines([...lines]);
        if (event === "interrupt") {
          try {
            const parsed = JSON.parse(dataJson);
            const pending: PendingTool[] = parsed?.interrupt_state?.pending_tools ?? [];
            if (pending.length > 0) {
              setInterruptState({ executionId, pendingTools: pending });
            }
          } catch {
            /* ignore */
          }
        }
      },
      signal,
    );
    const final = await api<Execution>(`/api/v1/agents/${id}/executions/${executionId}`);
    setLastExec(final);
  } catch (e) {
    if ((e as Error).name !== "AbortError") {
      setError(e instanceof Error ? e.message : "Resume failed");
    }
  } finally {
    setBusy(false);
  }
}

function handleInterruptCancel() {
  setInterruptState(null);
  setBusy(false);
  abortRef.current?.abort();
}
```

- [ ] **Step 4: Render the InterruptModal in the JSX**

In the `return (...)` block of `AgentDetailPage`, right before the closing `</div>` of the top-level container, add:

```tsx
{interruptState && (
  <InterruptModal
    executionId={interruptState.executionId}
    pendingTools={interruptState.pendingTools}
    onDecided={handleInterruptDecision}
    onCancel={handleInterruptCancel}
  />
)}
```

- [ ] **Step 5: Verify TypeScript compilation**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No type errors.

- [ ] **Step 6: Commit**

```bash
cd frontend && git add src/app/agents/\[id\]/page.tsx
git commit -m "feat(ui): wire InterruptModal into agent detail page for HITL resume flow"
```

---

### Task 3: Verify the interrupt flow end-to-end

- [ ] **Step 1: Create an agent with an interrupt config**

```bash
curl -s -X POST http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "HITL Test Agent",
    "graph_definition": {
      "nodes": [{"id": "n1", "type": "tool", "config": {"tool_name": "echo"}}],
      "edges": [],
      "entry_point": "n1"
    },
    "llm_model_config": {"provider": "mock", "model": "mock"},
    "interrupt_config": {"echo": "before"}
  }' | python3 -m json.tool
```

- [ ] **Step 2: Navigate to the agent in the browser and execute**

Open `http://localhost:3000/agents/<agent_id>`, click Execute. Expected: The modal appears asking to approve or reject the `echo` tool call.

- [ ] **Step 3: Approve and verify execution completes**

Click "Approve", then "Submit decisions". Expected: Execution resumes, output appears in the execution log.
