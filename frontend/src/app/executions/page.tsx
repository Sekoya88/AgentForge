"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";
import { EmptyState } from "@/components/ui/EmptyState";
import { StaggeredList } from "@/components/ui/StaggeredList";

type ExecutionRow = {
  id: string;
  agent_id: string;
  agent_name: string;
  status: string;
  duration_ms: number | null;
  started_at: string | null;
  completed_at: string | null;
  token_usage: Record<string, number> | null;
};

type ExecutionsResponse = {
  total: number;
  items: ExecutionRow[];
};

function statusBadge(s: string) {
  if (/complete|success/i.test(s))
    return "border-emerald-500/20 bg-emerald-500/10 text-emerald-400";
  if (/run|progress/i.test(s))
    return "border-amber-500/20 bg-amber-500/10 text-amber-400";
  if (/fail|error/i.test(s))
    return "border-red-500/20 bg-red-500/10 text-red-400";
  return "border-white/10 bg-white/5 text-af-muted";
}

export default function ExecutionsPage() {
  const router = useRouter();
  const [data, setData] = useState<ExecutionsResponse | null>(null);
  const [hasLangfuse, setHasLangfuse] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const limit = 25;

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const [d, s] = await Promise.all([
          api<ExecutionsResponse>(
            `/api/v1/dashboard/executions?limit=${limit}&offset=${page * limit}`,
          ),
          api<{ langfuse_configured: boolean }>("/api/v1/settings")
        ]);
        if (!c) {
          setData(d);
          setHasLangfuse(s.langfuse_configured);
        }
      } catch (e) {
        if (!c) {
          if (e instanceof ApiError && e.status === 401) {
            router.push("/login");
            return;
          }
          setError(e instanceof Error ? e.message : "Failed to load");
        }
      }
    })();
    return () => { c = true; };
  }, [page, router]);

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  return (
    <ToolShell active="executions">
      <div className="mx-auto max-w-6xl">
        <span className="af-kicker mb-2 block text-af-primary">[ EXECUTIONS ]</span>
        <h1 className="mb-8 font-sans text-3xl font-bold tracking-tight text-white md:text-4xl">
          Run <span className="af-serif-italic text-af-primary">history</span>
        </h1>

        {error && (
          <p className="mb-6 rounded-lg border border-af-error/30 bg-af-error/10 px-4 py-3 text-sm text-af-error">
            {error}
          </p>
        )}

        {!data && !error && <p className="text-af-muted">Loading...</p>}

        {data && data.items.length === 0 && (
          <EmptyState
            icon={<span className="material-symbols-outlined text-3xl">history</span>}
            title="No executions yet"
            description="Run an agent to see its execution history here. Each run is logged with status, duration, and token usage."
            action={{ label: "Go to agents", href: "/agents" }}
          />
        )}

        {data && data.items.length > 0 && (
          <>
            <div className="mb-4 text-xs text-af-muted">
              {data.total} execution{data.total !== 1 ? "s" : ""} total
            </div>
            <div className="overflow-hidden rounded-xl border border-af-border/40 bg-af-surface-container/40 backdrop-blur-sm">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-af-border/30 text-left text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                    <th className="px-4 py-3">ID</th>
                    <th className="px-4 py-3">Agent</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Duration</th>
                    <th className="px-4 py-3">Tokens</th>
                    <th className="px-4 py-3">Started</th>
                    <th className="px-4 py-3">Links</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-af-border/20">
                  <StaggeredList baseDelay={35}>
                    {data.items.map((ex) => (
                    <tr key={ex.id} className="af-card-interactive transition-colors hover:bg-white/[0.04]">
                      <td className="px-4 py-3 font-mono text-xs text-af-muted-dim">
                        {ex.id.slice(0, 8)}
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          href={`/agents/${ex.agent_id}`}
                          className="text-sm text-af-on-surface hover:text-af-primary"
                        >
                          {ex.agent_name}
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded border px-2 py-0.5 text-[10px] font-bold uppercase ${statusBadge(ex.status)}`}
                        >
                          {ex.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-af-muted">
                        {ex.duration_ms != null ? `${ex.duration_ms}ms` : "—"}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-af-muted">
                        {ex.token_usage?.total_tokens ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-af-muted-dim">
                        {ex.started_at ? new Date(ex.started_at).toLocaleString() : "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-af-muted-dim">
                        {hasLangfuse ? (
                          <a
                            href={`https://cloud.langfuse.com/project/traces/${ex.id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-af-primary underline decoration-white/20 underline-offset-2"
                          >
                            Langfuse ↗
                          </a>
                        ) : "—"}
                      </td>
                    </tr>
                  ))}
                  </StaggeredList>
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-center gap-3">
                <button
                  type="button"
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  className="rounded border border-af-border px-3 py-1 text-xs text-af-muted transition-colors hover:text-white disabled:opacity-30"
                >
                  ← Prev
                </button>
                <span className="text-xs text-af-muted">
                  Page {page + 1} of {totalPages}
                </span>
                <button
                  type="button"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded border border-af-border px-3 py-1 text-xs text-af-muted transition-colors hover:text-white disabled:opacity-30"
                >
                  Next →
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </ToolShell>
  );
}
