"use client";

type LogLine = { event: string; data: string; at: number };

export function ExecutionLog({ lines }: { lines: LogLine[] }) {
  if (lines.length === 0) return null;
  return (
    <div className="af-card border-af-border/80 bg-af-surface-void/50 p-4 font-mono text-xs text-af-on-surface">
      <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
        Execution stream
      </p>
      <ul className="max-h-64 space-y-1 overflow-y-auto">
        {lines.map((l, i) => (
          <li key={`${l.at}-${i}`} className="break-all">
            <span className="text-af-tertiary">{l.event}</span>
            <span className="text-af-muted-dim"> · </span>
            <span className="text-af-muted">{l.data}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
