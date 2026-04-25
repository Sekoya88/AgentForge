"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ExecutionTimeline } from "@/components/execution/ExecutionTimeline";
import { ApiError, api } from "@/lib/api";

type Message = { role: string; content: string };
type TokenUsage = { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };

type ExecutionDetail = {
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

function statusColor(s: string) {
  if (/complete|success/i.test(s)) return "border-emerald-500/30 bg-emerald-500/10 text-emerald-400";
  if (/run|progress/i.test(s)) return "border-amber-500/30 bg-amber-500/10 text-amber-400";
  if (/fail|error/i.test(s)) return "border-red-500/30 bg-red-500/10 text-red-400";
  return "border-white/10 bg-white/5 text-af-muted";
}

export default function ExecutionDetailPage() {
  const { executionId } = useParams<{ executionId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const agentId = searchParams.get("agent_id");

  const [exec, setExec] = useState<ExecutionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!agentId) {
      setError("Missing agent_id query param");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const data = await api<ExecutionDetail>(
          `/api/v1/agents/${agentId}/executions/${executionId}`,
        );
        if (!cancelled) setExec(data);
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 401) {
          router.push("/login");
          return;
        }
        setError(e instanceof Error ? e.message : "Failed to load execution");
      }
    })();
    return () => { cancelled = true; };
  }, [executionId, agentId, router]);

  return (
    <ToolShell active="executions">
      <div className="mx-auto max-w-4xl">
        {/* Breadcrumb */}
        <nav className="mb-6 flex items-center gap-2 text-xs text-af-muted-dim">
          <Link href="/executions" className="hover:text-af-primary transition-colors">
            Executions
          </Link>
          <span>/</span>
          <span className="font-mono text-af-muted">{executionId?.slice(0, 8)}…</span>
        </nav>

        <span className="af-kicker mb-2 block text-af-primary">[ EXECUTION DETAIL ]</span>
        <h1 className="mb-6 font-sans text-3xl font-bold tracking-tight text-white">
          Execution{" "}
          <span className="font-mono text-xl text-af-muted-dim">{executionId?.slice(0, 12)}…</span>
        </h1>

        {error && (
          <div className="mb-6 rounded-lg border border-af-error/30 bg-af-error/10 px-4 py-3 text-sm text-af-error">
            {error}
          </div>
        )}

        {!exec && !error && (
          <div className="text-sm text-af-muted">Loading execution…</div>
        )}

        {exec && (
          <div className="grid gap-6 lg:grid-cols-3">
            {/* Timeline — main column */}
            <div className="lg:col-span-2">
              <div className="rounded-xl border border-af-border/40 bg-af-surface-container/40 p-6 backdrop-blur-sm">
                <h2 className="mb-6 text-xs font-bold uppercase tracking-widest text-af-muted-dim">
                  Execution timeline
                </h2>
                <ExecutionTimeline exec={exec} />
              </div>

              {/* Output messages */}
              {exec.output_messages && exec.output_messages.length > 0 && (
                <div className="mt-4 rounded-xl border border-af-border/40 bg-af-surface-container/40 p-6 backdrop-blur-sm">
                  <h2 className="mb-4 text-xs font-bold uppercase tracking-widest text-af-muted-dim">
                    Full output
                  </h2>
                  <div className="space-y-3">
                    {exec.output_messages.map((msg, i) => (
                      <div key={i} className="rounded-lg border border-af-border/30 bg-af-surface-container/60 p-3">
                        <div className="mb-1.5 text-[10px] font-bold uppercase tracking-wider text-af-muted-dim">
                          {msg.role}
                        </div>
                        <p className="whitespace-pre-wrap text-sm text-af-on-surface leading-relaxed">
                          {msg.content}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Metadata sidebar */}
            <div className="space-y-4">
              <div className="rounded-xl border border-af-border/40 bg-af-surface-container/40 p-4 backdrop-blur-sm">
                <h2 className="mb-3 text-xs font-bold uppercase tracking-widest text-af-muted-dim">
                  Metadata
                </h2>
                <dl className="space-y-2.5 text-sm">
                  <div>
                    <dt className="text-[10px] uppercase tracking-wider text-af-muted-dim">Status</dt>
                    <dd className="mt-0.5">
                      <span className={`inline-block rounded border px-2 py-0.5 text-[10px] font-bold uppercase ${statusColor(exec.status)}`}>
                        {exec.status}
                      </span>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wider text-af-muted-dim">Duration</dt>
                    <dd className="mt-0.5 font-mono text-af-muted">
                      {exec.duration_ms != null ? `${exec.duration_ms}ms` : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wider text-af-muted-dim">Started</dt>
                    <dd className="mt-0.5 text-xs text-af-muted">
                      {exec.started_at ? new Date(exec.started_at).toLocaleString() : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wider text-af-muted-dim">Trigger</dt>
                    <dd className="mt-0.5 text-xs text-af-muted capitalize">
                      {exec.trigger_source ?? "api"}
                    </dd>
                  </div>
                </dl>
              </div>

              {exec.token_usage && (
                <div className="rounded-xl border border-af-border/40 bg-af-surface-container/40 p-4 backdrop-blur-sm">
                  <h2 className="mb-3 text-xs font-bold uppercase tracking-widest text-af-muted-dim">
                    Token usage
                  </h2>
                  <dl className="space-y-2 text-sm">
                    {exec.token_usage.prompt_tokens != null && (
                      <div className="flex justify-between">
                        <dt className="text-af-muted-dim">Prompt</dt>
                        <dd className="font-mono text-af-muted">{exec.token_usage.prompt_tokens.toLocaleString()}</dd>
                      </div>
                    )}
                    {exec.token_usage.completion_tokens != null && (
                      <div className="flex justify-between">
                        <dt className="text-af-muted-dim">Completion</dt>
                        <dd className="font-mono text-af-muted">{exec.token_usage.completion_tokens.toLocaleString()}</dd>
                      </div>
                    )}
                    {exec.token_usage.total_tokens != null && (
                      <div className="flex justify-between border-t border-af-border/30 pt-2">
                        <dt className="font-semibold text-af-on-surface">Total</dt>
                        <dd className="font-mono font-semibold text-af-primary">
                          {exec.token_usage.total_tokens.toLocaleString()}
                        </dd>
                      </div>
                    )}
                  </dl>
                </div>
              )}

              <Link
                href={`/agents/${exec.agent_id}`}
                className="flex items-center gap-2 rounded-xl border border-af-border/40 bg-af-surface-container/40 p-4 text-sm text-af-muted transition-colors hover:text-af-primary backdrop-blur-sm"
              >
                <span className="material-symbols-outlined text-base">smart_toy</span>
                View agent
              </Link>
            </div>
          </div>
        )}
      </div>
    </ToolShell>
  );
}
