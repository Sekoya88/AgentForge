"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";

type Campaign = {
  id: string;
  agent_id: string;
  status: string;
  overall_score: number | null;
  total_tests: number | null;
  created_at: string;
};

function statusBadge(status: string) {
  const s = status.toLowerCase();
  if (s.includes("run") || s.includes("progress"))
    return "border-emerald-500/20 bg-emerald-500/10 text-af-tertiary";
  if (s.includes("complete") || s.includes("done"))
    return "border-white/10 bg-white/5 text-af-muted";
  return "border-af-secondary/20 bg-af-secondary/10 text-af-secondary";
}

export default function CampaignsPage() {
  const router = useRouter();
  const [items, setItems] = useState<Campaign[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "running" | "completed">("all");

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const data = await api<Campaign[]>("/api/v1/campaigns");
        if (!c) setItems(data);
      } catch (e) {
        if (!c) {
          if (e instanceof ApiError && e.status === 401) router.push("/login");
          else setError(e instanceof Error ? e.message : "Failed");
        }
      }
    })();
    return () => {
      c = true;
    };
  }, [router]);

  const filtered = useMemo(() => {
    if (!items) return [];
    if (filter === "all") return items;
    return items.filter((x) => {
      const s = x.status.toLowerCase();
      if (filter === "running") return s.includes("run") || s.includes("progress");
      return s.includes("complete") || s.includes("done");
    });
  }, [items, filter]);

  return (
    <ToolShell active="campaigns">
      <header className="relative mb-12">
        <div className="mb-3 inline-block border border-af-primary/20 bg-af-primary/10 px-2 py-0.5 text-[10px] font-bold tracking-[0.2em] text-af-primary">
          [ CAMPAIGNS ]
        </div>
        <h1 className="text-4xl font-extrabold tracking-tighter text-af-on-surface md:text-5xl">
          Operational <span className="af-serif-italic font-normal text-af-primary">campaigns</span>
        </h1>
        <p className="mt-4 max-w-xl text-sm leading-relaxed text-af-muted">
          Red-team assessments launched from agent detail. API:{" "}
          <code className="text-af-muted-dim">POST /api/v1/campaigns</code>
        </p>
        <div className="mt-10 grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            ["Listed", items?.length ?? "—"],
            ["Active", items?.filter((i) => i.status.toLowerCase().includes("run")).length ?? "—"],
            ["With score", items?.filter((i) => i.overall_score != null).length ?? "—"],
            ["Agents", "—"],
          ].map(([k, v]) => (
            <div
              key={String(k)}
              className="rounded-xl border border-white/5 bg-af-surface-container p-5"
            >
              <div className="mb-1 text-[10px] uppercase tracking-widest text-af-muted-dim">{k}</div>
              <div className="text-2xl font-bold text-af-on-surface">{v}</div>
            </div>
          ))}
        </div>
      </header>

      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div className="flex gap-4">
          {(
            [
              ["all", "ALL CAMPAIGNS"],
              ["running", "RUNNING"],
              ["completed", "COMPLETED"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setFilter(key)}
              className={
                filter === key
                  ? "border-b-2 border-af-primary pb-1 text-xs font-bold text-af-on-surface"
                  : "pb-1 text-xs font-bold text-af-muted-dim transition-colors hover:text-af-on-surface"
              }
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className="mb-6 rounded-lg border border-af-error/30 bg-af-error/10 px-4 py-3 text-sm text-af-error">
          {error}
        </p>
      )}

      {items && items.length === 0 && (
        <div className="rounded-xl border border-dashed border-af-border/60 p-12 text-center">
          <p className="text-af-muted">No campaigns yet. Run red-team from an agent.</p>
          <Link href="/agents" className="mt-4 inline-block text-sm font-bold text-af-primary hover:underline">
            Go to agents →
          </Link>
        </div>
      )}

      {filtered.length > 0 && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((x) => (
            <Link
              key={x.id}
              href={`/campaigns/${x.id}`}
              className="group relative rounded-xl border border-af-border bg-af-surface-container p-6 transition-all hover:border-af-primary/30 hover:bg-af-surface-high/40 hover:shadow-[0_0_20px_rgba(79,70,229,0.08)]"
            >
              <div className="mb-6 flex justify-between gap-3">
                <div className="flex gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-af-indigo/20 text-af-primary">
                    <span className="material-symbols-outlined">data_object</span>
                  </div>
                  <div>
                    <h3 className="font-bold text-af-on-surface">Campaign {x.id.slice(0, 8)}…</h3>
                    <p className="text-[10px] text-af-muted-dim">
                      {new Date(x.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
                <span
                  className={`h-fit rounded border px-2 py-0.5 text-[10px] font-bold ${statusBadge(x.status)}`}
                >
                  {x.status.toUpperCase()}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4 border-t border-white/5 pt-4">
                <div>
                  <p className="mb-1 text-[10px] text-af-muted-dim">Score</p>
                  <p className="text-sm font-bold">{x.overall_score ?? "—"}</p>
                </div>
                <div>
                  <p className="mb-1 text-[10px] text-af-muted-dim">Tests</p>
                  <p className="text-sm font-bold">{x.total_tests ?? "—"}</p>
                </div>
              </div>
              <p className="mt-4 truncate font-mono text-[10px] text-af-muted">agent {x.agent_id}</p>
            </Link>
          ))}
        </div>
      )}
    </ToolShell>
  );
}
