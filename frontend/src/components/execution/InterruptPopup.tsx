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
            <AgentActivityIcon event={"interrupt" as unknown as AgentStep["event"]} size={40} />
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
