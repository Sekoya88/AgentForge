"use client";

import { AgentStep } from "@/types/chat";

type Props = {
  toasts: AgentStep[];
  isRunning: boolean;
  inline?: boolean;
};

type EventMeta = {
  icon: string;
  label: string;
  color: string;
  glowColor: string;
};

const EVENT_META: Record<string, EventMeta> = {
  agent_start:   { icon: "smart_toy",    label: "thinking",    color: "#a78bfa", glowColor: "rgba(167,139,250,0.3)" },
  tool_call:     { icon: "build",        label: "tool",        color: "#818cf8", glowColor: "rgba(129,140,248,0.3)" },
  tool_result:   { icon: "check_circle", label: "result",      color: "#818cf8", glowColor: "rgba(129,140,248,0.3)" },
  skill:         { icon: "psychology",   label: "skill",       color: "#c084fc", glowColor: "rgba(192,132,252,0.3)" },
  skill_summary: { icon: "psychology",   label: "skill",       color: "#c084fc", glowColor: "rgba(192,132,252,0.3)" },
  llm_start:     { icon: "auto_awesome", label: "generating",  color: "#e879f9", glowColor: "rgba(232,121,249,0.3)" },
  llm_end:       { icon: "auto_awesome", label: "generated",   color: "#e879f9", glowColor: "rgba(232,121,249,0.3)" },
  rag_search:    { icon: "search",       label: "searching",   color: "#38bdf8", glowColor: "rgba(56,189,248,0.3)" },
  complete:      { icon: "check",        label: "done",        color: "#34d399", glowColor: "rgba(52,211,153,0.3)" },
  error:         { icon: "error",        label: "error",       color: "#f87171", glowColor: "rgba(248,113,113,0.3)" },
};

function toastLabel(step: AgentStep): string {
  if (step.event === "complete") return "response ready";
  if (step.event === "error") return "execution error";
  return step.label || EVENT_META[step.event]?.label || step.event;
}

export function AgentToastStack({ toasts, isRunning, inline }: Props) {
  const visible = toasts.slice(-3);
  if (!isRunning && visible.length === 0) return null;

  return (
    <div className={`flex flex-col gap-1.5 ${inline ? "" : "mb-2"}`}>

      {/* Live generation indicator */}
      {isRunning && (
        <div
          className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm"
          style={{
            background: "rgba(79,70,229,0.12)",
            backdropFilter: "blur(16px)",
            WebkitBackdropFilter: "blur(16px)",
            border: "1px solid rgba(129,140,248,0.25)",
            boxShadow: "0 0 20px rgba(79,70,229,0.15)",
            animation: "af-morph-in 0.3s cubic-bezier(0.22,1,0.36,1) both",
          }}
        >
          <span
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"
            style={{
              background: "rgba(79,70,229,0.25)",
              border: "1px solid rgba(129,140,248,0.3)",
              boxShadow: "0 0 10px rgba(79,70,229,0.3)",
            }}
          >
            <span className="flex items-end gap-[2px] h-4">
              {[0.4, 0.75, 1, 0.85, 0.6].map((h, i) => (
                <span
                  key={i}
                  className="w-[2px] rounded-full block"
                  style={{
                    height: `${h * 14}px`,
                    background: "#818cf8",
                    animation: `af-wave 1s ${i * 0.1}s ease-in-out infinite`,
                    transformOrigin: "bottom",
                  }}
                />
              ))}
            </span>
          </span>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "#818cf8" }}>
              Forge
            </div>
            <div className="text-xs text-af-muted">generating response…</div>
          </div>
        </div>
      )}

      {/* Recent activity steps — stacked perspective */}
      {[...visible].reverse().map((step, idx) => {
        const meta = EVENT_META[step.event] ?? { icon: "info", label: step.event, color: "#a6a6c4", glowColor: "rgba(166,166,196,0.2)" };
        const opacity = 1 - idx * 0.28;
        const scale = 1 - idx * 0.03;
        return (
          <div
            key={`${step.timestamp}-${idx}`}
            className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm"
            style={{
              opacity,
              transform: `scale(${scale})`,
              transformOrigin: "top center",
              background: idx === 0 ? "var(--af-glass-medium)" : "var(--af-glass-subtle)",
              backdropFilter: "blur(12px)",
              WebkitBackdropFilter: "blur(12px)",
              border: `1px solid ${idx === 0 ? meta.glowColor : "var(--af-glass-border)"}`,
              boxShadow: idx === 0 ? `0 0 16px ${meta.glowColor}` : "none",
              transition: "all 0.2s ease",
            }}
          >
            <span
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"
              style={{
                background: `${meta.glowColor.replace("0.3", "0.15")}`,
                border: `1px solid ${meta.glowColor}`,
              }}
            >
              <span
                className="material-symbols-outlined text-sm"
                style={{
                  color: meta.color,
                  filter: idx === 0 ? `drop-shadow(0 0 4px ${meta.color})` : "none",
                }}
              >
                {meta.icon}
              </span>
            </span>
            <div>
              <div
                className="text-[10px] font-bold uppercase tracking-widest"
                style={{ color: `${meta.color}cc` }}
              >
                {meta.label}
              </div>
              <div className="text-xs text-af-on-surface">{toastLabel(step)}</div>
            </div>
          </div>
        );
      })}

      <style>{`
        @keyframes af-wave {
          0%, 100% { transform: scaleY(0.35); }
          50% { transform: scaleY(1); }
        }
      `}</style>
    </div>
  );
}
