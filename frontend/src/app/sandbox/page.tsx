"use client";

import { useState } from "react";
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
        const res = await api<{ job_id: string; exit_code: number | null; stdout: string; stderr: string }>(
          "/api/v1/sandbox/run",
          {
            method: "POST",
            body: JSON.stringify({
              code,
              language: "python",
              run_async: false,
            }),
          },
        );
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
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Sandbox</h1>
      <p className="text-sm text-neutral-500">
        Python subprocess on the API host (dev only). Async mode streams Redis events.
      </p>
      <textarea
        value={code}
        onChange={(e) => setCode(e.target.value)}
        rows={8}
        className="w-full rounded-md border border-neutral-700 bg-neutral-900 p-3 font-mono text-sm"
      />
      <div className="flex gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => run(true)}
          className="rounded-md bg-cyan-500 px-3 py-1.5 text-sm font-medium text-black disabled:opacity-50"
        >
          Run sync
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => run(false)}
          className="rounded-md border border-neutral-600 px-3 py-1.5 text-sm disabled:opacity-50"
        >
          Run + stream
        </button>
      </div>
      {err && <p className="text-sm text-red-400">{err}</p>}
      {out && (
        <pre className="rounded-md border border-neutral-800 bg-black/30 p-3 text-xs text-neutral-300">{out}</pre>
      )}
      {lines.length > 0 && (
        <pre className="max-h-48 overflow-auto rounded-md border border-neutral-800 bg-black/30 p-3 text-xs text-neutral-300">
          {lines.join("\n")}
        </pre>
      )}
    </div>
  );
}
