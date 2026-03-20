"use client";

type LogLine = { event: string; data: string; at: number };

export function ExecutionLog({ lines }: { lines: LogLine[] }) {
  if (lines.length === 0) return null;
  return (
    <div className="rounded-lg border border-neutral-800 bg-black/40 p-3 font-mono text-xs text-neutral-300">
      <p className="mb-2 text-[10px] uppercase tracking-wider text-neutral-500">Execution stream</p>
      <ul className="max-h-64 space-y-1 overflow-y-auto">
        {lines.map((l, i) => (
          <li key={`${l.at}-${i}`} className="break-all">
            <span className="text-cyan-500/90">{l.event}</span>
            <span className="text-neutral-600"> · </span>
            <span>{l.data}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
