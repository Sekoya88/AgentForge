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
};

export default function CampaignDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [c, setC] = useState<Campaign | null>(null);
  const [error, setError] = useState<string | null>(null);

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
    return () => {
      x = true;
    };
  }, [id, router]);

  if (error && !c)
    return (
      <ToolShell active="campaigns">
        <p className="text-af-error">{error}</p>
      </ToolShell>
    );
  if (!c)
    return (
      <ToolShell active="campaigns">
        <p className="text-af-muted">Loading…</p>
      </ToolShell>
    );

  return (
    <ToolShell active="campaigns">
      <Link href="/campaigns" className="mb-6 inline-block text-sm text-af-muted hover:text-af-primary">
        ← Campaigns
      </Link>
      <span className="af-kicker mb-2 block text-af-primary">[ CAMPAIGN ]</span>
      <h1 className="mb-2 font-sans text-3xl font-bold text-white">Report</h1>
      <p className="mb-8 text-sm text-af-muted">
        Agent <span className="font-mono text-af-on-surface">{c.agent_id}</span> · {c.status}
      </p>
      <div className="mb-8 grid gap-4 sm:grid-cols-3">
        {[
          ["Score", c.overall_score ?? "—"],
          ["Passed", c.passed_tests ?? "—"],
          ["Failed", c.failed_tests ?? "—"],
        ].map(([label, val]) => (
          <div key={String(label)} className="af-card p-5">
            <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">{label}</p>
            <p className="mt-2 text-2xl font-bold text-af-on-surface">{val}</p>
          </div>
        ))}
      </div>
      <div className="af-card bg-af-surface-void/40 p-6">
        <p className="text-sm font-bold text-af-muted">Report JSON</p>
        <pre className="mt-3 max-h-[420px] overflow-auto text-xs text-af-muted">
          {JSON.stringify(c.report, null, 2)}
        </pre>
      </div>
    </ToolShell>
  );
}
