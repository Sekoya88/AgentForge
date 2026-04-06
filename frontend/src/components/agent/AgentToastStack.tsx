// frontend/src/components/agent/AgentToastStack.tsx
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
  color: string; // tailwind text color
};

const EVENT_META: Record<string, EventMeta> = {
  agent_start:   { icon: "smart_toy",    label: "thinking",    color: "text-purple-300" },
  tool_call:     { icon: "build",        label: "tool",        color: "text-indigo-300" },
  tool_result:   { icon: "check_circle", label: "result",      color: "text-indigo-300" },
  skill:         { icon: "psychology",   label: "skill",       color: "text-violet-300" },
  skill_summary: { icon: "psychology",   label: "skill",       color: "text-violet-300" },
  llm_start:     { icon: "auto_awesome", label: "generating",  color: "text-fuchsia-300" },
  llm_end:       { icon: "auto_awesome", label: "generated",   color: "text-fuchsia-300" },
  rag_search:    { icon: "search",       label: "searching",   color: "text-sky-300" },
  complete:      { icon: "check",        label: "done",        color: "text-emerald-300" },
  error:         { icon: "error",        label: "error",       color: "text-red-300" },
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
        <div className="flex items-center gap-2.5 rounded-xl border border-indigo-500/20 bg-af-surface-high px-3 py-2 text-sm animate-in fade-in slide-in-from-bottom-2 duration-300">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-950/80 border border-indigo-800/40">
            {/* Animated waveform */}
            <span className="flex items-end gap-[2px] h-4">
              {[0.4, 0.75, 1, 0.85, 0.6].map((h, i) => (
                <span
                  key={i}
                  className="w-[2px] rounded-full bg-indigo-400 block"
                  style={{
                    height: `${h * 14}px`,
                    animation: `af-wave 1s ${i * 0.1}s ease-in-out infinite`,
                    transformOrigin: "bottom",
                  }}
                />
              ))}
            </span>
          </span>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">Forge</div>
            <div className="text-xs text-af-muted">generating response…</div>
          </div>
        </div>
      )}

      {/* Recent activity steps */}
      {[...visible].reverse().map((step, idx) => {
        const meta = EVENT_META[step.event] ?? { icon: "info", label: step.event, color: "text-af-muted" };
        return (
          <div
            key={`${step.timestamp}-${idx}`}
            className="flex items-center gap-2.5 rounded-xl border border-af-border/60 bg-af-surface-high px-3 py-2 text-sm transition-all duration-200"
            style={{ opacity: 1 - idx * 0.25, transform: `scale(${1 - idx * 0.025})`, transformOrigin: "top center" }}
          >
            <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-white/5 bg-af-surface-container`}>
              <span className={`material-symbols-outlined text-sm ${meta.color}`}>{meta.icon}</span>
            </span>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
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
