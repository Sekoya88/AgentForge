"use client";

type LogLine = { event: string; data: string; at: number };

function AudioPlayer({ dataJson }: { dataJson: string }) {
  try {
    const { audio_b64 } = JSON.parse(dataJson) as { audio_b64: string };
    const src = `data:audio/mp3;base64,${audio_b64}`;
    return (
      <audio controls src={src} className="mt-1 h-8 w-full max-w-md" preload="metadata" />
    );
  } catch {
    return <span className="text-af-error">invalid audio data</span>;
  }
}

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
            {l.event === "audio" ? (
              <AudioPlayer dataJson={l.data} />
            ) : (
              <span className="text-af-muted">{l.data}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ExecutionAudioInline({ audioB64 }: { audioB64: string }) {
  const src = `data:audio/mp3;base64,${audioB64}`;
  return (
    <div className="mt-4">
      <p className="mb-1 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
        Output audio
      </p>
      <audio controls src={src} className="h-9 w-full max-w-md" preload="metadata" />
    </div>
  );
}
