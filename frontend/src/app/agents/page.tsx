"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";

type Agent = {
  id: string;
  name: string;
  status: string;
  description: string | null;
};

export default function AgentsPage() {
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
            setError("Unauthorized — login first.");
          } else {
            setError(e instanceof Error ? e.message : "Failed to load");
          }
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Agents</h1>
        <Link
          href="/agents/new"
          className="rounded-md bg-cyan-500 px-3 py-1.5 text-sm font-medium text-black"
        >
          New agent
        </Link>
      </div>
      {error && <p className="text-sm text-amber-400">{error}</p>}
      {agents && agents.length === 0 && (
        <p className="text-neutral-500">No agents yet. Create one to get started.</p>
      )}
      {agents && agents.length > 0 && (
        <ul className="divide-y divide-neutral-800 rounded-lg border border-neutral-800">
          {agents.map((a) => (
            <li key={a.id} className="flex items-center justify-between px-4 py-3">
              <div>
                <Link href={`/agents/${a.id}`} className="font-medium hover:text-cyan-400">
                  {a.name}
                </Link>
                <p className="text-xs text-neutral-500">{a.status}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
