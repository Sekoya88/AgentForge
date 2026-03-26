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
