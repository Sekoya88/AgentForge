"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";

type Campaign = {
  id: string;
  agent_id: string;
  status: string;
  overall_score: number | null;
  total_tests: number | null;
  created_at: string;
};

export default function CampaignsPage() {
  const router = useRouter();
  const [items, setItems] = useState<Campaign[] | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Red-team campaigns</h1>
      <p className="text-sm text-neutral-500">
        Launch assessments from an agent detail page (API:{" "}
        <code className="text-neutral-400">POST /api/v1/campaigns</code>).
      </p>
      {error && <p className="text-sm text-amber-400">{error}</p>}
      {items && items.length === 0 && (
        <p className="text-neutral-500">No campaigns yet.</p>
      )}
      {items && items.length > 0 && (
        <ul className="divide-y divide-neutral-800 rounded-lg border border-neutral-800">
          {items.map((x) => (
            <li key={x.id} className="px-4 py-3">
              <Link href={`/campaigns/${x.id}`} className="font-medium hover:text-cyan-400">
                Campaign {x.id.slice(0, 8)}…
              </Link>
              <p className="text-xs text-neutral-500">
                {x.status} · score {x.overall_score ?? "—"} · tests {x.total_tests ?? "—"}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
