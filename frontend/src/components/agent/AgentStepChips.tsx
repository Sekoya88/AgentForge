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
