"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ExecutionLog } from "@/components/execution/ExecutionLog";
import { ApiError, api } from "@/lib/api";
import { consumeExecutionSse } from "@/lib/sse";
import { ChatUI } from "@/components/chat/ChatUI";

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

  if (error && !agent) return <p className="px-4 text-af-error">{error}</p>;
  if (!agent) return <p className="px-4 text-af-muted">Loading…</p>;

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-8 md:px-8">
      <Link href="/agents" className="text-sm text-af-muted hover:text-af-primary">
        ← Agents
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <span className="af-kicker text-af-primary">[ AGENT ]</span>
          <h1 className="mt-2 font-sans text-3xl font-bold text-white">{agent.name}</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/agents/${id}/builder`}
            className="rounded-lg border border-af-border px-4 py-2 text-sm text-af-on-surface transition-colors hover:border-af-primary hover:text-af-primary"
          >
            Open builder
          </Link>
          <button
            type="button"
            onClick={runCampaign}
            disabled={campaignBusy}
            className="rounded-lg border border-af-secondary/40 bg-af-secondary/10 px-4 py-2 text-sm font-bold text-af-secondary transition-all hover:bg-af-secondary/20 flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {campaignBusy ? (
              <>
                <span className="material-symbols-outlined animate-spin text-sm">autorenew</span>
                Red-team…
              </>
            ) : (
              "Run red-team"
            )}
          </button>
        </div>
      </div>
      {agent.security_score != null && (
        <p className="text-sm text-af-muted">
          Security score: <span className="text-af-tertiary">{agent.security_score}</span>
        </p>
      )}
      <div className="af-card space-y-4 p-6">
        <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">model_config</p>
        <pre className="overflow-x-auto text-xs text-af-muted">
          {JSON.stringify(agent.model_config, null, 2)}
        </pre>
      </div>
      <div className="af-card space-y-4 p-6">
        <label className="flex items-center gap-2 text-sm text-af-muted">
          <input
            type="checkbox"
            checked={useStream}
            onChange={(e) => setUseStream(e.target.checked)}
            className="rounded border-af-border"
          />
          Stream logs (async + SSE, needs Redis)
        </label>
        <label className="block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
          User message
        </label>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="af-input max-w-lg"
        />
        <button
          type="button"
          onClick={run}
          disabled={busy || !input.trim()}
          className="af-btn-primary flex items-center justify-center gap-2 px-6 py-2 text-sm disabled:opacity-50"
        >
          {busy ? (
            <>
              <span className="material-symbols-outlined animate-spin text-sm">autorenew</span>
              Running…
            </>
          ) : (
            "Execute"
          )}
        </button>
      </div>
      {error && <p className="text-sm text-af-error">{error}</p>}
      <ExecutionLog lines={streamLines} />
      {lastExec && (
        <div className="af-card p-6">
          <div className="mb-6 flex items-center justify-between">
            <h3 className="font-bold text-white">Execution Result</h3>
            <span className="text-xs text-af-muted">
              Status: {lastExec.status} · {lastExec.duration_ms ?? "?"} ms
            </span>
          </div>
          <ChatUI
            messages={
              (lastExec.output_messages as {
                role: "user" | "assistant" | "system" | "tool";
                content: string;
              }[]) || []
            }
          />
        </div>
      )}
    </div>
  );
}
