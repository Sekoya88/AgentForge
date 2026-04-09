"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";
import { EmptyState } from "@/components/ui/EmptyState";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type HubAgent = {
  id: string;
  name: string;
  description: string | null;
  stars: number;
  security_score: number | null;
  status: string;
  graph_node_count: number;
};

function SecurityBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  const pct = Math.round(score * 100);
  const color =
    pct >= 80
      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
      : pct >= 50
        ? "bg-yellow-500/20 text-yellow-300 border-yellow-500/30"
        : "bg-red-500/20 text-red-300 border-red-500/30";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-bold ${color}`}>
      Shield {pct}%
    </span>
  );
}

function AgentCard({
  agent,
  onStar,
  onClone,
  busy,
}: {
  agent: HubAgent;
  onStar: (id: string) => void;
  onClone: (id: string) => void;
  busy: string | null;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-af-border bg-af-surface-dim p-5 transition-all hover:border-af-primary/40 hover:shadow-[0_0_20px_rgba(79,70,229,0.15)]">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-base font-bold text-af-on-surface">{agent.name}</h3>
        <SecurityBadge score={agent.security_score} />
      </div>

      {agent.description && (
        <p className="text-sm text-af-muted line-clamp-2">{agent.description}</p>
      )}

      <div className="flex items-center gap-3 text-xs text-af-muted">
        <span className="flex items-center gap-1">
          <span className="material-symbols-outlined text-sm">account_tree</span>
          {agent.graph_node_count} node{agent.graph_node_count !== 1 ? "s" : ""}
        </span>
        <span className="flex items-center gap-1">
          <span className="material-symbols-outlined text-sm">circle</span>
          {agent.status}
        </span>
      </div>

      <div className="mt-auto flex items-center gap-2 pt-1">
        <button
          onClick={() => onStar(agent.id)}
          disabled={busy === `star-${agent.id}`}
          className="flex items-center gap-1.5 rounded-lg border border-af-border px-3 py-1.5 text-xs font-semibold text-af-on-surface transition-all hover:border-yellow-500/50 hover:bg-yellow-500/10 hover:text-yellow-300 disabled:opacity-50"
        >
          <span className="material-symbols-outlined text-sm">star</span>
          {agent.stars}
        </button>
        <button
          onClick={() => onClone(agent.id)}
          disabled={busy === `clone-${agent.id}`}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-af-primary px-3 py-1.5 text-xs font-bold text-white transition-all hover:bg-af-primary/80 disabled:opacity-50"
        >
          {busy === `clone-${agent.id}` ? (
            "Cloning..."
          ) : (
            <>
              <span className="material-symbols-outlined text-sm">content_copy</span>
              Clone to workspace
            </>
          )}
        </button>
      </div>
    </div>
  );
}

export default function HubPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<HubAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const load = useCallback(async (q: string) => {
    setLoading(true);
    setError(null);
    try {
      const url = new URL(`${API_BASE}/api/v1/hub/agents`);
      if (q) url.searchParams.set("search", q);
      url.searchParams.set("limit", "50");
      const res = await fetch(url.toString());
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as { agents: HubAgent[]; total: number };
      setAgents(data.agents);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load hub");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(query);
  }, [load, query]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setQuery(search);
  };

  const handleStar = async (id: string) => {
    setBusy(`star-${id}`);
    try {
      await api(`/api/v1/hub/agents/${id}/star`, { method: "POST" });
      setAgents((prev) => prev.map((a) => (a.id === id ? { ...a, stars: a.stars + 1 } : a)));
      showToast("Starred!");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        router.push("/login");
      } else {
        showToast(e instanceof Error ? e.message : "Failed to star");
      }
    } finally {
      setBusy(null);
    }
  };

  const handleClone = async (id: string) => {
    setBusy(`clone-${id}`);
    try {
      await api<{ agent_id: string; name: string }>(`/api/v1/hub/agents/${id}/clone`, {
        method: "POST",
      });
      showToast("Agent cloned to your workspace!");
      setTimeout(() => router.push("/agents"), 1200);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        router.push("/login");
      } else {
        showToast(e instanceof Error ? e.message : "Failed to clone");
      }
      setBusy(null);
    }
  };

  return (
    <ToolShell active="hub">
      <div className="mx-auto max-w-6xl space-y-8">
        {/* Header */}
        <div className="space-y-1">
          <h1 className="text-3xl font-black tracking-tight text-af-on-surface">
            AgentForge Hub
          </h1>
          <p className="text-af-muted">
            Discover and clone public agents built by the community.
          </p>
        </div>

        {/* Search */}
        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="relative flex-1">
            <span className="material-symbols-outlined pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-af-muted">
              search
            </span>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search agents..."
              className="w-full rounded-lg border border-af-border bg-af-surface-dim py-2.5 pl-10 pr-4 text-sm text-af-on-surface placeholder:text-af-muted focus:border-af-primary focus:outline-none focus:ring-1 focus:ring-af-primary"
            />
          </div>
          <button
            type="submit"
            className="rounded-lg bg-af-primary px-5 py-2.5 text-sm font-bold text-white hover:bg-af-primary/80"
          >
            Search
          </button>
          {query && (
            <button
              type="button"
              onClick={() => { setSearch(""); setQuery(""); }}
              className="rounded-lg border border-af-border px-4 py-2.5 text-sm text-af-muted hover:text-af-on-surface"
            >
              Clear
            </button>
          )}
        </form>

        {/* Stats bar */}
        {!loading && !error && agents.length > 0 && (
          <p className="text-xs text-af-muted">
            {`${agents.length} agent${agents.length !== 1 ? "s" : ""} in the hub${query ? ` matching "${query}"` : ""}`}
          </p>
        )}

        {/* Content */}
        {loading && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-44 animate-pulse rounded-xl border border-af-border bg-af-surface-dim"
              />
            ))}
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-center text-red-300">
            {error}
          </div>
        )}

        {!loading && !error && agents.length === 0 && (
          <EmptyState
            icon="hub"
            title="No agents here yet"
            description="Publish your own agents to share them with the community."
            action={{ label: "Go to my agents", href: "/agents" }}
          />
        )}

        {!loading && !error && agents.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {agents.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                onStar={handleStar}
                onClone={handleClone}
                busy={busy}
              />
            ))}
          </div>
        )}
      </div>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 rounded-xl border border-af-border bg-af-surface-dim px-5 py-3 text-sm font-semibold text-af-on-surface shadow-2xl">
          {toast}
        </div>
      )}
    </ToolShell>
  );
}
