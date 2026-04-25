// frontend/src/components/agent/AgentActivityIcon.tsx
"use client";

import { AgentStep } from "@/types/chat";

type Props = {
  event: AgentStep["event"] | "agent_start";
  size?: number;
};

const EVENT_ICONS: Record<string, { icon: string; bg: string; color: string }> = {
  agent_start:   { icon: "smart_toy",    bg: "#1a0d2e", color: "#c084fc" },
  tool_call:     { icon: "build",        bg: "#0d1427", color: "#818cf8" },
  tool_result:   { icon: "check_circle", bg: "#0d1427", color: "#818cf8" },
  skill:         { icon: "psychology",   bg: "#130d2e", color: "#a78bfa" },
  skill_summary: { icon: "psychology",   bg: "#130d2e", color: "#a78bfa" },
  llm_start:     { icon: "auto_awesome", bg: "#1a0d22", color: "#e879f9" },
  llm_end:       { icon: "auto_awesome", bg: "#1a0d22", color: "#e879f9" },
  rag_search:    { icon: "search",       bg: "#0d1f2e", color: "#38bdf8" },
  complete:      { icon: "check",        bg: "#0a1a0f", color: "#4ade80" },
  error:         { icon: "error",        bg: "#1a0a0a", color: "#f87171" },
};

/**
 * Renders an animated icon for a given agent event type using Material Symbols.
 */
export function AgentActivityIcon({ event, size = 28 }: Props) {
  const cfg = EVENT_ICONS[event] ?? EVENT_ICONS.tool_call;
  const r = Math.round(size * 0.32);

  const isSpinning = event === "agent_start" || event === "llm_start";
  const isBouncing = event === "tool_call";

  return (
    <>
      {(isSpinning || isBouncing) && (
        <style>{`
          @keyframes af-spin { to { transform: rotate(360deg); } }
          @keyframes af-bounce-icon { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-2px); } }
        `}</style>
      )}
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: size,
          height: size,
          borderRadius: r,
          background: cfg.bg,
          border: "1px solid rgba(255,255,255,0.06)",
          flexShrink: 0,
        }}
      >
        <span
          className="material-symbols-outlined"
          style={{
            fontSize: Math.round(size * 0.52),
            color: cfg.color,
            lineHeight: 1,
            animation: isSpinning
              ? "af-spin 2s linear infinite"
              : isBouncing
              ? "af-bounce-icon 0.8s ease-in-out infinite"
              : undefined,
          }}
        >
          {cfg.icon}
        </span>
      </span>
    </>
  );
}

/** Waveform bars for "generating response" state */
export function WaveformIcon({ color = "#818cf8", height = 20 }: { color?: string; height?: number }) {
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
          <span
            key={i}
            style={{
              width: 2.5,
              height: height * h,
              borderRadius: 2,
              background: color,
              display: "block",
              animation: `af-wave 1s ${i * 0.1}s ease-in-out infinite`,
              transformOrigin: "bottom",
            }}
          />
        ))}
      </span>
    </>
  );
}
