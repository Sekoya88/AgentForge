"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";

type Campaign = {
  id: string;
  agent_id: string;
  status: string;
  overall_score: number | null;
  total_tests: number | null;
  passed_tests: number | null;
  failed_tests: number | null;
  report: Record<string, unknown> | null;
  vulnerabilities: Record<string, unknown> | null;
  created_at: string;
  completed_at: string | null;
};

function scoreColor(score: number) {
  if (score >= 80) return "text-emerald-400";
  if (score >= 50) return "text-amber-400";
  return "text-red-400";
}

function statusBadge(s: string) {
  if (/complete/i.test(s)) return "border-emerald-500/20 bg-emerald-500/10 text-emerald-400";
  if (/run/i.test(s)) return "border-amber-500/20 bg-amber-500/10 text-amber-400";
  if (/fail/i.test(s)) return "border-red-500/20 bg-red-500/10 text-red-400";
  return "border-white/10 bg-white/5 text-af-muted";
}

export default function CampaignDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [c, setC] = useState<Campaign | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let x = false;
    (async () => {
      try {
        const data = await api<Campaign>(`/api/v1/campaigns/${id}`);
        if (!x) setC(data);
      } catch (e) {
        if (!x) {
          if (e instanceof ApiError && e.status === 401) router.push("/login");
          else setError(e instanceof Error ? e.message : "Load failed");
        }
      }
    })();
    return () => { x = true; };
  }, [id, router]);

  async function del() {
    if (!confirm("Delete this campaign permanently?")) return;
    setDeleting(true);
    try {
      await api(`/api/v1/campaigns/${id}`, { method: "DELETE" });
      router.push("/campaigns");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
      setDeleting(false);
    }
  }

  if (error && !c) return <ToolShell active="campaigns"><p className="text-af-error">{error}</p></ToolShell>;
  if (!c) return <ToolShell active="campaigns"><p className="text-af-muted">Loading...</p></ToolShell>;

  const passRate = c.total_tests ? Math.round(((c.passed_tests ?? 0) / c.total_tests) * 100) : null;
  const vulnEntries = c.vulnerabilities ? Object.entries(c.vulnerabilities) : [];
  const reportEntries = c.report ? Object.entries(c.report) : [];

  return (
    <ToolShell active="campaigns">
      <Link href="/campaigns" className="mb-6 inline-block text-sm text-af-muted hover:text-af-primary">
        ← Campaigns
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <span className="af-kicker mb-2 block text-af-primary">[ CAMPAIGN REPORT ]</span>
          <h1 className="font-sans text-3xl font-bold text-white">Security Assessment</h1>
          <div className="mt-2 flex items-center gap-3">
            <span className={`rounded border px-2 py-0.5 text-[10px] font-bold uppercase ${statusBadge(c.status)}`}>
              {c.status}
            </span>
            <Link
              href={`/agents/${c.agent_id}`}
              className="font-mono text-xs text-af-muted hover:text-af-primary"
            >
              agent {c.agent_id.slice(0, 8)}...
            </Link>
          </div>
        </div>
        <button
          type="button"
          onClick={del}
          disabled={deleting}
          className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-400 hover:bg-red-500/20 disabled:opacity-50"
        >
          Delete
        </button>
      </div>

      {/* Score overview */}
      <section className="mt-8 grid gap-4 sm:grid-cols-4">
        <div className="af-card flex flex-col items-center p-6">
          <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">Score</p>
          <p className={`mt-2 text-4xl font-bold ${c.overall_score != null ? scoreColor(c.overall_score) : "text-af-muted"}`}>
            {c.overall_score ?? "—"}
          </p>
          {passRate != null && <p className="mt-1 text-xs text-af-muted">{passRate}% pass rate</p>}
        </div>
        <div className="af-card p-6 text-center">
          <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">Total</p>
          <p className="mt-2 text-2xl font-bold text-white">{c.total_tests ?? "—"}</p>
          <p className="mt-1 text-xs text-af-muted">tests</p>
        </div>
        <div className="af-card p-6 text-center">
          <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">Passed</p>
          <p className="mt-2 text-2xl font-bold text-emerald-400">{c.passed_tests ?? "—"}</p>
        </div>
        <div className="af-card p-6 text-center">
          <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">Failed</p>
          <p className="mt-2 text-2xl font-bold text-red-400">{c.failed_tests ?? "—"}</p>
        </div>
      </section>

      {/* Vulnerabilities */}
      {vulnEntries.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-4 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
            Vulnerabilities ({vulnEntries.length})
          </h2>
          <div className="space-y-3">
            {vulnEntries.map(([key, val]) => (
              <div key={key} className="af-card p-4">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm text-red-400">warning</span>
                  <span className="font-mono text-sm font-bold text-white">{key}</span>
                </div>
                <pre className="mt-2 overflow-x-auto text-xs text-af-muted">
                  {typeof val === "string" ? val : JSON.stringify(val, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Report details */}
      {reportEntries.length > 0 && (
        <section className="mt-8">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Report detail
            </h2>
            <button
              type="button"
              onClick={() => setShowRaw(!showRaw)}
              className="text-xs text-af-muted hover:text-white"
            >
              {showRaw ? "Structured view" : "Raw JSON"}
            </button>
          </div>
          {showRaw ? (
            <pre className="af-card max-h-[500px] overflow-auto p-6 text-xs text-af-muted">
              {JSON.stringify(c.report, null, 2)}
            </pre>
          ) : (
            <div className="space-y-3">
              {reportEntries.map(([key, val]) => (
                <div key={key} className="af-card p-4">
                  <p className="mb-2 font-mono text-xs font-bold text-af-primary">{key}</p>
                  <pre className="overflow-x-auto text-xs text-af-muted">
                    {typeof val === "string" ? val : JSON.stringify(val, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Timestamps */}
      <section className="mt-8 text-xs text-af-muted-dim">
        <p>Created: {c.created_at ? new Date(c.created_at).toLocaleString() : "—"}</p>
        {c.completed_at && <p>Completed: {new Date(c.completed_at).toLocaleString()}</p>}
        <p className="mt-1 font-mono">ID: {c.id}</p>
      </section>
    </ToolShell>
  );
}
