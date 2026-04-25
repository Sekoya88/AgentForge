// frontend/src/components/execution/InterruptPopup.tsx
"use client";

import { useState } from "react";
import { AgentActivityIcon } from "@/components/agent/AgentActivityIcon";
import { AgentStep } from "@/types/chat";

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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-sm"
      style={{ background: "rgba(0,0,0,0.65)" }}
    >
      <div
        className="mx-4 w-full max-w-[480px] rounded-2xl p-6"
        style={{
          background: "var(--af-glass-heavy)",
          backdropFilter: "blur(32px)",
          WebkitBackdropFilter: "blur(32px)",
          border: "1px solid rgba(167,139,250,0.4)",
          boxShadow: "0 0 24px rgba(167,139,250,0.2), 0 20px 60px rgba(0,0,0,0.4)",
          animation: "af-morph-in 0.4s cubic-bezier(0.22,1,0.36,1) both",
        }}
      >
        {/* Header */}
        <div className="mb-5 flex items-center gap-3">
          <AgentActivityIcon event={"interrupt" as unknown as AgentStep["event"]} size={40} />
          <div>
            <div className="text-base font-bold text-af-on-surface">Approbation humaine requise</div>
            <div className="mt-0.5 text-xs text-af-muted">
              Exécution en pause ·{" "}
              <span className="font-mono text-[11px] text-af-secondary">
                {executionId.slice(0, 8)}…
              </span>
            </div>
          </div>
        </div>

        {/* Tool cards */}
        <div className="flex flex-col gap-3">
          {pendingTools.map((tool, idx) => {
            const d = decisions[tool.tool_name];
            return (
              <div
                key={tool.tool_name}
                className="rounded-xl p-4"
                style={{
                  background: "var(--af-glass-medium)",
                  border: "1px solid var(--af-glass-border-hover)",
                }}
              >
                {/* Tool name */}
                <div className="mb-3 flex items-center gap-2 font-mono text-[13px] font-bold text-af-secondary">
                  <span className="material-symbols-outlined text-sm">build</span>
                  {tool.tool_name}
                  <span className="ml-auto font-sans text-[10px] font-normal text-af-muted-dim">
                    call #{idx + 1}
                  </span>
                </div>

                {/* Decision buttons */}
                <div className="mb-3 flex gap-2">
                  <button
                    type="button"
                    onClick={() => setDecision(tool.tool_name, "decision", "approve")}
                    className="flex-1 rounded-lg py-2 text-xs font-semibold transition-all"
                    style={{
                      background: d?.decision === "approve" ? "rgba(52,211,153,0.2)" : "var(--af-glass-subtle)",
                      color: "#34d399",
                      border: `1px solid ${d?.decision === "approve" ? "rgba(52,211,153,0.4)" : "var(--af-glass-border)"}`,
                      boxShadow: d?.decision === "approve" ? "0 0 12px rgba(52,211,153,0.2)" : "none",
                    }}
                  >
                    ✓ Approuver
                  </button>
                  <button
                    type="button"
                    onClick={() => setDecision(tool.tool_name, "decision", "reject")}
                    className="flex-1 rounded-lg py-2 text-xs font-semibold transition-all"
                    style={{
                      background: d?.decision === "reject" ? "rgba(248,113,113,0.2)" : "var(--af-glass-subtle)",
                      color: "#f87171",
                      border: `1px solid ${d?.decision === "reject" ? "rgba(248,113,113,0.4)" : "var(--af-glass-border)"}`,
                      boxShadow: d?.decision === "reject" ? "0 0 12px rgba(248,113,113,0.2)" : "none",
                    }}
                  >
                    ✕ Rejeter
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setDecision(tool.tool_name, "decision", "approve");
                      document.getElementById(`arg-${tool.tool_name}`)?.focus();
                    }}
                    className="flex-1 rounded-lg py-2 text-xs font-semibold transition-all"
                    style={{
                      background: "var(--af-glass-subtle)",
                      color: "#a78bfa",
                      border: "1px solid var(--af-glass-border)",
                    }}
                  >
                    ✎ Modifier
                  </button>
                </div>

                {/* Argument */}
                <div className="mb-1.5 text-[10px] font-bold uppercase tracking-wider text-af-muted-dim">
                  Argument
                </div>
                <textarea
                  id={`arg-${tool.tool_name}`}
                  value={d?.arg ?? ""}
                  onChange={(e) => setDecision(tool.tool_name, "arg", e.target.value)}
                  disabled={d?.decision === "reject"}
                  rows={2}
                  className="w-full resize-none rounded-lg px-3 py-2 font-mono text-[11px] text-af-on-surface placeholder-af-muted-dim outline-none focus:ring-1 focus:ring-af-primary/50 disabled:opacity-40"
                  style={{
                    background: "var(--af-glass-subtle)",
                    border: "1px solid var(--af-glass-border)",
                  }}
                />
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="mt-5 flex gap-2.5">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 rounded-lg border border-af-border/60 py-2.5 text-sm text-af-muted transition-colors hover:border-af-border hover:text-af-on-surface"
          >
            Annuler l&apos;exécution
          </button>
          <button
            type="button"
            onClick={() => onDecided(Object.values(decisions))}
            className="flex-[2] rounded-lg py-2.5 text-sm font-bold text-white transition-all hover:opacity-90"
            style={{
              background: "linear-gradient(135deg, #7c3aed, #a78bfa)",
              boxShadow: "0 0 20px rgba(124,58,237,0.3)",
            }}
          >
            Envoyer les décisions →
          </button>
        </div>
      </div>
    </div>
  );
}
