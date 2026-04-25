// frontend/src/components/agent/AgentStepChips.tsx
"use client";

import { AgentStep } from "@/types/chat";

type Props = {
  steps: AgentStep[];
};

type ChipConfig = {
  icon: string;
  bg: string;
  text: string;
  border: string;
};

const CHIP_CONFIG: Record<AgentStep["event"], ChipConfig> = {
  tool_call:     { icon: "build",         bg: "bg-indigo-950/80",  text: "text-indigo-300",  border: "border-indigo-800/60" },
  tool_result:   { icon: "check_circle",  bg: "bg-indigo-950/80",  text: "text-indigo-300",  border: "border-indigo-800/60" },
  skill:         { icon: "psychology",    bg: "bg-violet-950/80",  text: "text-violet-300",  border: "border-violet-800/60" },
  skill_summary: { icon: "psychology",    bg: "bg-violet-950/80",  text: "text-violet-300",  border: "border-violet-800/60" },
  agent_start:   { icon: "smart_toy",     bg: "bg-purple-950/80",  text: "text-purple-300",  border: "border-purple-800/60" },
  agent_end:     { icon: "smart_toy",     bg: "bg-purple-950/80",  text: "text-purple-300",  border: "border-purple-800/60" },
  llm_start:     { icon: "auto_awesome",  bg: "bg-fuchsia-950/80", text: "text-fuchsia-300", border: "border-fuchsia-800/60" },
  llm_end:       { icon: "auto_awesome",  bg: "bg-fuchsia-950/80", text: "text-fuchsia-300", border: "border-fuchsia-800/60" },
  rag_search:    { icon: "search",        bg: "bg-sky-950/80",     text: "text-sky-300",     border: "border-sky-800/60" },
  complete:      { icon: "check",         bg: "bg-emerald-950/80", text: "text-emerald-300", border: "border-emerald-800/60" },
  error:         { icon: "error",         bg: "bg-red-950/80",     text: "text-red-300",     border: "border-red-800/60" },
};

export function AgentStepChips({ steps }: Props) {
  const visible = steps.filter((s) =>
    s.event === "tool_call" ||
    s.event === "skill" ||
    s.event === "skill_summary" ||
    s.event === "rag_search" ||
    s.event === "complete" ||
    s.event === "error"
  );

  if (visible.length === 0) return null;

  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {visible.map((step, i) => {
        const cfg = CHIP_CONFIG[step.event] ?? CHIP_CONFIG.tool_call;
        const label =
          step.event === "complete"
            ? step.durationMs
              ? `${(step.durationMs / 1000).toFixed(1)}s`
              : "done"
            : step.label + (step.durationMs ? ` · ${(step.durationMs / 1000).toFixed(1)}s` : "");

        return (
          <span
            key={i}
            className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[10px] font-semibold tracking-wide ${cfg.bg} ${cfg.text} ${cfg.border}`}
          >
            <span className="material-symbols-outlined text-[11px] leading-none">{cfg.icon}</span>
            {label}
          </span>
        );
      })}
    </div>
  );
}
