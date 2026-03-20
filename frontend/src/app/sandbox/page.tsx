"use client";

import { useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";
import { consumeSsePath } from "@/lib/sse";

export default function SandboxPage() {
  const [code, setCode] = useState("print(2 + 2)");
  const [out, setOut] = useState("");
  const [lines, setLines] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(sync: boolean) {
    setErr(null);
    setOut("");
    setLines([]);
    setBusy(true);
    try {
      if (sync) {
        const res = await api<{
          job_id: string;
          exit_code: number | null;
          stdout: string;
          stderr: string;
        }>("/api/v1/sandbox/run", {
          method: "POST",
          body: JSON.stringify({
            code,
            language: "python",
            run_async: false,
          }),
        });
        setOut(`${res.stdout}\n${res.stderr}`.trim() + `\n(exit ${res.exit_code})`);
      } else {
        const res = await api<{ job_id: string }>("/api/v1/sandbox/run", {
          method: "POST",
          body: JSON.stringify({
            code,
            language: "python",
            run_async: true,
          }),
        });
        const acc: string[] = [];
        await consumeSsePath(`/api/v1/sandbox/stream/${res.job_id}`, (ev, data) => {
          acc.push(`${ev}: ${data}`);
          setLines([...acc]);
        });
      }
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ToolShell active="sandbox">
      <header className="mb-8 space-y-2">
        <div className="flex items-center gap-3">
          <span className="rounded border border-af-primary/20 bg-af-primary/10 px-2 py-0.5 text-[10px] font-bold tracking-[0.2em] text-af-primary">
            [ SANDBOX ]
          </span>
          <div className="h-px flex-1 bg-gradient-to-r from-af-primary/20 to-transparent" />
        </div>
        <h1 className="font-sans text-3xl font-bold tracking-tight text-white md:text-4xl">
          Virtual <span className="af-serif-italic text-af-primary">Intelligence</span> Playground
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-af-muted">
          Python on the API host (dev). Async streams Redis events via SSE.
        </p>
      </header>

      <div className="mb-6 flex items-start gap-4 rounded-r-xl border-l-4 border-af-error/50 bg-af-error/10 p-4">
        <span className="material-symbols-outlined text-af-error">report</span>
        <div>
          <h4 className="mb-1 text-xs font-bold uppercase tracking-wider text-af-error">
            Safety protocols
          </h4>
          <p className="text-xs leading-relaxed text-af-muted">
            Sandbox execution is isolated; throttle and quotas apply in production.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        <div className="flex flex-col overflow-hidden rounded-xl border border-af-border bg-af-surface-container shadow-2xl xl:col-span-8">
          <div className="flex h-10 items-center justify-between border-b border-af-border/80 bg-af-surface-high/50 px-4">
            <div className="flex items-center gap-2">
              <div className="flex gap-1.5">
                <div className="h-2.5 w-2.5 rounded-full bg-af-error/40" />
                <div className="h-2.5 w-2.5 rounded-full bg-af-secondary/40" />
                <div className="h-2.5 w-2.5 rounded-full bg-af-tertiary/40" />
              </div>
              <span className="ml-4 text-[10px] font-bold tracking-widest text-af-muted-dim uppercase">
                sandbox.py
              </span>
            </div>
            <span className="text-xs text-af-muted-dim">Python 3</span>
          </div>
          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            rows={14}
            className="min-h-[320px] flex-1 resize-y border-0 bg-af-surface-void p-6 font-mono text-sm leading-6 text-af-on-surface focus:ring-0"
          />
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-af-border/80 p-4">
            <span className="flex items-center gap-1 text-[10px] text-af-tertiary">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-af-tertiary" />
              Ready
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => run(true)}
                className="af-btn-primary px-5 py-2 text-xs disabled:opacity-50"
              >
                Run sync
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => run(false)}
                className="rounded-lg border border-af-border px-5 py-2 text-xs font-bold text-af-on-surface transition-colors hover:bg-white/5 disabled:opacity-50"
              >
                Run + stream
              </button>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-6 xl:col-span-4">
          <div className="flex flex-1 flex-col overflow-hidden rounded-xl border border-af-border bg-af-surface-high/30">
            <div className="flex items-center justify-between border-b border-af-border/80 px-4 py-2">
              <span className="text-[10px] font-bold uppercase text-af-muted">Output</span>
            </div>
            <div className="max-h-[280px] flex-1 overflow-y-auto p-4 font-mono text-[11px] text-af-secondary xl:max-h-none">
              {err && <p className="text-af-error">{err}</p>}
              {out && <pre className="whitespace-pre-wrap text-af-muted">{out}</pre>}
              {lines.length > 0 && (
                <pre className="mt-2 whitespace-pre-wrap text-af-muted">{lines.join("\n")}</pre>
              )}
              {!err && !out && lines.length === 0 && (
                <span className="text-af-muted-dim">Awaiting run…</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </ToolShell>
  );
}
