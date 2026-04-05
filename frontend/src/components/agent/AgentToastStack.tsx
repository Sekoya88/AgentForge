// frontend/src/components/agent/AgentToastStack.tsx
"use client";

import { AgentStep } from "@/types/chat";
import { AgentActivityIcon, WaveformIcon } from "./AgentActivityIcon";

type Props = {
  toasts: AgentStep[];
  isRunning: boolean;
  inline?: boolean;
};

function toastLabel(step: AgentStep): string {
  if (step.event === "agent_start") return `réfléchit · ${step.label}`;
  if (step.event === "tool_call")   return step.label;
  if (step.event === "complete")    return "réponse générée";
  if (step.event === "error")       return "erreur";
  return step.label;
}

/**
 * Renders up to 3 live toasts stacked, newest on top.
 * Toasts auto-clear when `isRunning` becomes false (handled by useAgentActivity).
 * Positioned as a block element — the parent positions it where needed.
 */
export function AgentToastStack({ toasts, isRunning, inline }: Props) {
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
      <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: inline ? 0 : 8 }}>
        {isRunning && (
          <div style={{
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
