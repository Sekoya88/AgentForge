"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
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

  if (error && !c) return <p className="text-red-400">{error}</p>;
  if (!c) return <p className="text-neutral-500">Loading…</p>;

  return (
    <div className="space-y-6">
      <Link href="/campaigns" className="text-sm text-neutral-500 hover:text-white">
        ← Campaigns
      </Link>
      <h1 className="text-2xl font-semibold">Campaign</h1>
      <p className="text-sm text-neutral-400">
        Agent <span className="font-mono text-neutral-300">{c.agent_id}</span> · {c.status}
      </p>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-lg border border-neutral-800 p-4">
          <p className="text-xs text-neutral-500">Score</p>
          <p className="text-xl font-semibold">{c.overall_score ?? "—"}</p>
        </div>
        <div className="rounded-lg border border-neutral-800 p-4">
          <p className="text-xs text-neutral-500">Passed</p>
          <p className="text-xl font-semibold">{c.passed_tests ?? "—"}</p>
        </div>
        <div className="rounded-lg border border-neutral-800 p-4">
          <p className="text-xs text-neutral-500">Failed</p>
          <p className="text-xl font-semibold">{c.failed_tests ?? "—"}</p>
        </div>
      </div>
      <div className="rounded-lg border border-neutral-800 bg-neutral-950 p-4">
        <p className="text-sm text-neutral-500">Report</p>
        <pre className="mt-2 overflow-x-auto text-xs text-neutral-300">
          {JSON.stringify(c.report, null, 2)}
        </pre>
      </div>
    </div>
  );
}
