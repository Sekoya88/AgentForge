"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";

type Agent = {
  id: string;
  name: string;
  status: string;
  description: string | null;
};

function statusStyle(status: string) {
  const s = status.toLowerCase();
  if (s.includes("run") || s === "active")
    return "border-af-tertiary/20 bg-af-tertiary/10 text-af-tertiary";
  if (s.includes("pause"))
    return "border-af-primary/20 bg-af-primary/10 text-af-primary";
  return "border-white/10 bg-white/5 text-af-muted";
}

export default function AgentsPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api<Agent[]>("/api/v1/agents");
        if (!cancelled) setAgents(data);
      } catch (e) {
        if (!cancelled) {
          if (e instanceof ApiError && e.status === 401) {
            router.push("/login");
            return;
          }
          setError(e instanceof Error ? e.message : "Failed to load");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <div className="mx-auto max-w-7xl px-4 pb-16 pt-8 md:px-8">
      <header className="mb-12">
        <div className="mb-2 flex items-baseline gap-2">
          <span className="af-kicker text-af-primary">[ AGENTS ]</span>
        </div>
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <h1 className="font-sans text-5xl font-bold tracking-tighter text-af-on-surface md:text-7xl">
            Your <span className="af-serif-italic text-af-primary">fleet</span>
          </h1>
          <Link
            href="/agents/new"
            className="af-btn-primary inline-flex items-center justify-center gap-2 px-8 py-3 text-sm"
          >
            <span className="material-symbols-outlined text-sm">add</span>
            New agent
          </Link>
        </div>
      </header>

      <section className="mb-10 grid grid-cols-1 gap-6 md:grid-cols-4">
        <div className="flex flex-col justify-between rounded-xl border border-white/5 bg-af-surface-container p-6">
          <span className="text-[0.65rem] uppercase tracking-widest text-af-muted-dim">Agents</span>
          <span className="text-3xl font-bold text-af-tertiary">{agents?.length ?? "—"}</span>
        </div>
        <div className="flex flex-col justify-between rounded-xl border border-white/5 bg-af-surface-container p-6">
          <span className="text-[0.65rem] uppercase tracking-widest text-af-muted-dim">Status</span>
          <span className="text-3xl font-bold text-af-on-surface">Live</span>
        </div>
        <div className="flex flex-col justify-between rounded-xl border border-white/5 bg-af-surface-container p-6 md:col-span-2">
          <span className="text-[0.65rem] uppercase tracking-widest text-af-muted-dim">Console</span>
          <span className="text-sm text-af-muted">Manage graphs, execute runs, stream SSE.</span>
        </div>
      </section>

      {error && (
        <p className="mb-6 rounded-lg border border-af-error/30 bg-af-error/10 px-4 py-3 text-sm text-af-error">
          {error}
        </p>
      )}

      {agents && agents.length === 0 && (
        <div className="rounded-xl border border-dashed border-af-border/60 p-12 text-center">
          <p className="text-af-muted">No agents yet. Create one to get started.</p>
          <Link href="/agents/new" className="mt-4 inline-block text-sm font-bold text-af-primary hover:underline">
            New agent →
          </Link>
        </div>
      )}

      {agents && agents.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-af-border/40 bg-af-surface-container/40 backdrop-blur-sm">
          <div className="divide-y divide-af-border">
            {agents.map((a) => (
              <div
                key={a.id}
                className="group flex flex-col justify-between gap-4 p-6 transition-colors hover:bg-white/[0.02] md:flex-row md:items-center"
              >
                <div className="flex items-center gap-6">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-white/10 bg-af-surface-high transition-colors group-hover:border-af-primary/50">
                    <span className="material-symbols-outlined text-af-primary">smart_toy</span>
                  </div>
                  <div>
                    <div className="mb-1 flex flex-wrap items-center gap-3">
                      <Link
                        href={`/agents/${a.id}`}
                        className="text-lg font-bold text-af-on-surface hover:text-af-primary"
                      >
                        {a.name}
                      </Link>
                      <span
                        className={`rounded border px-2 py-0.5 text-[0.65rem] font-bold uppercase tracking-tighter ${statusStyle(a.status)}`}
                      >
                        [ {a.status} ]
                      </span>
                    </div>
                    {a.description && (
                      <p className="max-w-md text-xs text-af-muted">{a.description}</p>
                    )}
                  </div>
                </div>
                <Link
                  href={`/agents/${a.id}/builder`}
                  className="text-xs font-bold text-af-muted hover:text-af-primary md:shrink-0"
                >
                  Builder →
                </Link>
              </div>
            ))}
          </div>
        </div>
      )}

      <footer className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-white/5 py-8 font-mono text-xs uppercase tracking-widest text-slate-500 md:flex-row">
        <span>AgentForge</span>
        <div className="flex gap-6">
          <Link href="/" className="hover:text-indigo-400">
            Home
          </Link>
          <Link href="/sandbox" className="hover:text-indigo-400">
            Sandbox
          </Link>
        </div>
      </footer>
    </div>
  );
}
