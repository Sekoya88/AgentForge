"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ExecutionLog } from "@/components/execution/ExecutionLog";
import { ApiError, api } from "@/lib/api";
import { consumeExecutionSse } from "@/lib/sse";

type Agent = {
  id: string;
  name: string;
  graph_definition: Record<string, unknown>;
  model_config: Record<string, unknown>;
  security_score: number | null;
};

type Execution = {
  id: string;
  status: string;
  output_messages: unknown[] | null;
  duration_ms: number | null;
};

type LogLine = { event: string; data: string; at: number };

export default function AgentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [agent, setAgent] = useState<Agent | null>(null);
  const [lastExec, setLastExec] = useState<Execution | null>(null);
  const [streamLines, setStreamLines] = useState<LogLine[]>([]);
  const [input, setInput] = useState("Hello");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [campaignBusy, setCampaignBusy] = useState(false);
  const [useStream, setUseStream] = useState(true);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const a = await api<Agent>(`/api/v1/agents/${id}`);
        if (!c) setAgent(a);
      } catch (e) {
        if (!c) {
          if (e instanceof ApiError && e.status === 401) router.push("/login");
          else setError(e instanceof Error ? e.message : "Load failed");
        }
      }
    })();
    return () => {
      c = true;
      abortRef.current?.abort();
    };
  }, [id, router]);

  async function run() {
    setBusy(true);
    setError(null);
    setStreamLines([]);
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    const signal = abortRef.current.signal;

    try {
      if (useStream) {
        const ex = await api<Execution>(`/api/v1/agents/${id}/execute`, {
          method: "POST",
          body: JSON.stringify({
            input_messages: [{ role: "user", content: input }],
            run_async: true,
          }),
        });
        if (ex.status !== "running") {
          setLastExec(ex);
          setBusy(false);
          return;
        }
        const lines: LogLine[] = [];
        await consumeExecutionSse(
          id,
          ex.id,
          (event, dataJson) => {
            lines.push({ event, data: dataJson, at: Date.now() });
            setStreamLines([...lines]);
          },
          signal,
        );
        const final = await api<Execution>(`/api/v1/agents/${id}/executions/${ex.id}`);
        setLastExec(final);
      } else {
        const ex = await api<Execution>(`/api/v1/agents/${id}/execute`, {
          method: "POST",
          body: JSON.stringify({
            input_messages: [{ role: "user", content: input }],
            run_async: false,
          }),
        });
        setLastExec(ex);
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setError(e instanceof Error ? e.message : "Execute failed");
    } finally {
      setBusy(false);
    }
  }

  async function runCampaign() {
    setCampaignBusy(true);
    setError(null);
    try {
      await api(`/api/v1/campaigns`, {
        method: "POST",
        body: JSON.stringify({
          agent_id: id,
          plugins: ["default"],
          strategies: ["basic"],
          run_async: false,
        }),
      });
      const a = await api<Agent>(`/api/v1/agents/${id}`);
      setAgent(a);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Campaign failed");
    } finally {
      setCampaignBusy(false);
    }
  }

  if (error && !agent) return <p className="text-red-400">{error}</p>;
  if (!agent) return <p className="text-neutral-500">Loading…</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/agents" className="text-sm text-neutral-500 hover:text-white">
          ← Agents
        </Link>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{agent.name}</h1>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/agents/${id}/builder`}
            className="rounded-md border border-neutral-600 px-3 py-1.5 text-sm text-neutral-200 hover:border-cyan-500"
          >
            Open builder
          </Link>
          <button
            type="button"
            onClick={runCampaign}
            disabled={campaignBusy}
            className="rounded-md border border-amber-700/80 bg-amber-950/40 px-3 py-1.5 text-sm text-amber-200 disabled:opacity-50"
          >
            {campaignBusy ? "Red-team…" : "Run red-team"}
          </button>
        </div>
      </div>
      {agent.security_score != null && (
        <p className="text-sm text-neutral-400">
          Security score: <span className="text-cyan-400">{agent.security_score}</span>
        </p>
      )}
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm text-neutral-400">
          <input
            type="checkbox"
            checked={useStream}
            onChange={(e) => setUseStream(e.target.checked)}
          />
          Stream logs (async + SSE, needs Redis)
        </label>
        <label className="block text-sm text-neutral-400">User message</label>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="w-full max-w-lg rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        />
        <button
          type="button"
          onClick={run}
          disabled={busy}
          className="mt-2 rounded-md bg-cyan-500 px-4 py-2 text-sm font-medium text-black disabled:opacity-50"
        >
          {busy ? "Running…" : "Execute"}
        </button>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <ExecutionLog lines={streamLines} />
      {lastExec && (
        <div className="rounded-lg border border-neutral-800 bg-neutral-950 p-4">
          <p className="text-sm text-neutral-400">
            Status: {lastExec.status} · {lastExec.duration_ms ?? "?"} ms
          </p>
          <pre className="mt-2 overflow-x-auto text-xs text-neutral-300">
            {JSON.stringify(lastExec.output_messages, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
