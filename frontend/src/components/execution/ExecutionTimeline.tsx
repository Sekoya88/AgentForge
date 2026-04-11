"use client";

import { useMemo } from "react";
import { useScrollReveal } from "@/hooks/useScrollReveal";

type Message = { role: string; content: string };
type TokenUsage = { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };

type Execution = {
  id: string;
  agent_id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  token_usage: TokenUsage | null;
  input_messages: Message[];
  output_messages: Message[] | null;
  trigger_source?: string;
};

type TimelineEvent = {
  label: string;
  sublabel?: string;
  timestamp: string | null;
  offsetMs: number | null;
  icon: string;
  color: string;
  glowColor: string;
  content?: string;
};

function truncate(s: string, n = 120) {
  return s.length > n ? s.slice(0, n) + "…" : s;
}

function fmtMs(ms: number | null) {
  if (ms == null) return "—";
  if (ms < 1000) return `+${ms}ms`;
  return `+${(ms / 1000).toFixed(2)}s`;
}

function TimelineRow({ evt, pct, isLast, index }: {
  evt: TimelineEvent;
  pct: number | null;
  isLast: boolean;
  index: number;
}) {
  const [ref, visible] = useScrollReveal<HTMLDivElement>({ threshold: 0.1 });

  return (
    <div
      ref={ref}
      className="flex gap-4"
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "none" : "translateX(-12px)",
        transition: `opacity 0.4s ease ${index * 60}ms, transform 0.4s ease ${index * 60}ms`,
      }}
    >
      {/* Spine */}
      <div className="flex flex-col items-center">
        <div
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border transition-all"
          style={{
            borderColor: `${evt.glowColor}40`,
            background: `${evt.glowColor}15`,
            boxShadow: visible ? `0 0 12px ${evt.glowColor}30` : "none",
          }}
        >
          <span
            className="material-symbols-outlined text-base"
            style={{
              color: evt.color.replace("text-", ""),
              filter: `drop-shadow(0 0 4px ${evt.glowColor}60)`,
            }}
          >
            {evt.icon}
          </span>
        </div>
        {!isLast && (
          <div
            className="w-px flex-1 my-0.5 transition-all duration-700"
            style={{
              background: visible
                ? `linear-gradient(to bottom, ${evt.glowColor}40, transparent)`
                : "var(--af-glass-border)",
            }}
          />
        )}
      </div>

      {/* Content bubble */}
      <div className="pb-5 min-w-0 flex-1">
        <div className="flex items-baseline gap-2 flex-wrap mb-1">
          <span className="text-sm font-semibold text-af-on-surface">{evt.label}</span>
          {evt.sublabel && (
            <span
              className="text-[10px] uppercase tracking-wider rounded px-1.5 py-0.5 font-mono"
              style={{
                color: evt.color.replace("text-", ""),
                border: `1px solid ${evt.glowColor}30`,
                background: `${evt.glowColor}10`,
              }}
            >
              {evt.sublabel}
            </span>
          )}
          <span className="ml-auto font-mono text-xs text-af-muted-dim">{fmtMs(evt.offsetMs)}</span>
        </div>

        {/* Progress bar */}
        {pct != null && !isLast && (
          <div className="mt-1.5 h-0.5 w-full rounded-full bg-af-border/20 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-1000 ease-out"
              style={{
                width: visible ? `${pct}%` : "0%",
                background: `linear-gradient(90deg, ${evt.glowColor}60, ${evt.glowColor})`,
                boxShadow: `0 0 6px ${evt.glowColor}40`,
              }}
            />
          </div>
        )}

        {evt.content && (
          <div
            className="mt-2 rounded-lg px-3 py-2 font-mono text-[11px] text-af-muted leading-relaxed whitespace-pre-wrap break-words"
            style={{
              background: "var(--af-glass-medium)",
              border: `1px solid ${evt.glowColor}20`,
              backdropFilter: "blur(8px)",
              WebkitBackdropFilter: "blur(8px)",
            }}
          >
            {evt.content}
          </div>
        )}
      </div>
    </div>
  );
}

export function ExecutionTimeline({ exec }: { exec: Execution }) {
  const events = useMemo<TimelineEvent[]>(() => {
    const evts: TimelineEvent[] = [];

    evts.push({
      label: "Execution triggered",
      sublabel: exec.trigger_source ?? "api",
      timestamp: exec.started_at,
      offsetMs: 0,
      icon: "play_circle",
      color: "text-af-primary",
      glowColor: "#c3c0ff",
      content: exec.input_messages
        .filter((m) => m.role === "user")
        .map((m) => truncate(m.content))
        .join("\n") || undefined,
    });

    const outputs = exec.output_messages ?? [];
    const durationMs = exec.duration_ms ?? 0;

    outputs.forEach((msg, idx) => {
      const fraction = outputs.length > 1 ? (idx + 1) / outputs.length : 0.8;
      const isTool = msg.role === "tool";
      evts.push({
        label: isTool ? "Tool call" : `Node output ${idx + 1}`,
        sublabel: msg.role,
        timestamp: null,
        offsetMs: Math.round(durationMs * fraction * 0.9),
        icon: isTool ? "build" : "smart_toy",
        color: isTool ? "text-amber-400" : "text-emerald-400",
        glowColor: isTool ? "#f59e0b" : "#34d399",
        content: truncate(msg.content),
      });
    });

    const statusOk = /complete|success/i.test(exec.status);
    evts.push({
      label: statusOk ? "Completed" : exec.status,
      sublabel: exec.duration_ms != null ? `${exec.duration_ms}ms total` : undefined,
      timestamp: exec.completed_at,
      offsetMs: exec.duration_ms,
      icon: statusOk ? "check_circle" : "error",
      color: statusOk ? "text-emerald-400" : "text-red-400",
      glowColor: statusOk ? "#34d399" : "#f87171",
    });

    return evts;
  }, [exec]);

  const total = exec.duration_ms ?? 1;

  return (
    <div className="space-y-0">
      {events.map((evt, i) => {
        const pct = evt.offsetMs != null ? Math.min(100, (evt.offsetMs / total) * 100) : null;
        return (
          <TimelineRow
            key={i}
            evt={evt}
            pct={pct}
            isLast={i === events.length - 1}
            index={i}
          />
        );
      })}
    </div>
  );
}
