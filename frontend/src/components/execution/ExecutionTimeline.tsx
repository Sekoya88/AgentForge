"use client";

import { useMemo } from "react";

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

export function ExecutionTimeline({ exec }: { exec: Execution }) {
  const events = useMemo<TimelineEvent[]>(() => {
    const evts: TimelineEvent[] = [];

    // Trigger event
    evts.push({
      label: "Execution triggered",
      sublabel: exec.trigger_source ?? "api",
      timestamp: exec.started_at,
      offsetMs: 0,
      icon: "play_circle",
      color: "text-af-primary",
      content: exec.input_messages
        .filter((m) => m.role === "user")
        .map((m) => truncate(m.content))
        .join("\n") || undefined,
    });

    // For each output message, create a step (simulating nodes)
    const outputs = exec.output_messages ?? [];
    const durationMs = exec.duration_ms ?? 0;

    outputs.forEach((msg, idx) => {
      const fraction = outputs.length > 1 ? (idx + 1) / outputs.length : 0.8;
      evts.push({
        label: msg.role === "tool" ? "Tool call" : `Node output ${idx + 1}`,
        sublabel: msg.role,
        timestamp: null,
        offsetMs: Math.round(durationMs * fraction * 0.9),
        icon: msg.role === "tool" ? "build" : "smart_toy",
        color: msg.role === "tool" ? "text-amber-400" : "text-emerald-400",
        content: truncate(msg.content),
      });
    });

    // Completion event
    const statusOk = /complete|success/i.test(exec.status);
    evts.push({
      label: statusOk ? "Completed" : exec.status,
      sublabel: exec.duration_ms != null ? `${exec.duration_ms}ms total` : undefined,
      timestamp: exec.completed_at,
      offsetMs: exec.duration_ms,
      icon: statusOk ? "check_circle" : "error",
      color: statusOk ? "text-emerald-400" : "text-red-400",
    });

    return evts;
  }, [exec]);

  const total = exec.duration_ms ?? 1;

  return (
    <div className="space-y-0">
      {events.map((evt, i) => {
        const pct = evt.offsetMs != null ? Math.min(100, (evt.offsetMs / total) * 100) : null;
        const isLast = i === events.length - 1;

        return (
          <div key={i} className="flex gap-4">
            {/* Timeline spine */}
            <div className="flex flex-col items-center">
              <div
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-af-border/50 bg-af-surface-container ${evt.color}`}
              >
                <span className="material-symbols-outlined text-base">{evt.icon}</span>
              </div>
              {!isLast && (
                <div className="w-px flex-1 bg-gradient-to-b from-af-border/50 to-af-border/10 my-0.5" />
              )}
            </div>

            {/* Content */}
            <div className={`pb-5 min-w-0 flex-1 ${isLast ? "" : ""}`}>
              <div className="flex items-baseline gap-2 flex-wrap">
                <span className="text-sm font-semibold text-af-on-surface">{evt.label}</span>
                {evt.sublabel && (
                  <span className="text-[10px] uppercase tracking-wider text-af-muted-dim rounded border border-af-border/40 px-1.5 py-0.5">
                    {evt.sublabel}
                  </span>
                )}
                <span className="ml-auto font-mono text-xs text-af-muted-dim">
                  {fmtMs(evt.offsetMs)}
                </span>
              </div>

              {/* Progress bar showing relative position in execution */}
              {pct != null && !isLast && (
                <div className="mt-1.5 h-0.5 w-full rounded-full bg-af-border/20 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-af-primary/40 transition-all"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              )}

              {evt.content && (
                <p className="mt-2 rounded-lg border border-af-border/30 bg-af-surface-container/60 px-3 py-2 font-mono text-[11px] text-af-muted leading-relaxed whitespace-pre-wrap break-words">
                  {evt.content}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
