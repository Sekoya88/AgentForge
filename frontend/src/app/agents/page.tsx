"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { useChatContext } from "@/contexts/ChatContext";
import { ApiError, API_BASE, api } from "@/lib/api";
import { useScrollReveal } from "@/hooks/useScrollReveal";

type Agent = {
  id: string;
  name: string;
  status: string;
  description: string | null;
  health_score?: number | null;
};

function statusMeta(status: string): { label: string; color: string; glow: string } {
  const s = status.toLowerCase();
  if (s.includes("run") || s === "active")
    return { label: status, color: "#3cddc7", glow: "rgba(60,221,199,0.25)" };
  if (s.includes("pause"))
    return { label: status, color: "#c3c0ff", glow: "rgba(195,192,255,0.25)" };
  return { label: status, color: "#6b7280", glow: "rgba(107,114,128,0.15)" };
}

function healthColor(score: number): string {
  if (score >= 80) return "#34d399";
  if (score >= 50) return "#f59e0b";
  return "#f87171";
}

function AgentCard({
  agent,
  onChat,
  onExport,
  onCopySDK,
  onDelete,
  copiedId,
  deletingId,
  index,
}: {
  agent: Agent;
  onChat: () => void;
  onExport: () => void;
  onCopySDK: () => void;
  onDelete: () => void;
  copiedId: string | null;
  deletingId: string | null;
  index: number;
}) {
  const [ref, visible] = useScrollReveal<HTMLDivElement>({ threshold: 0.1 });
  const meta = statusMeta(agent.status);
  const health = agent.health_score;

  return (
    <div
      ref={ref}
      className="group flex flex-col rounded-xl p-5 transition-all duration-300"
      style={{
        background: "var(--af-glass-medium)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        border: "1px solid var(--af-glass-border)",
        opacity: visible ? 1 : 0,
        transform: visible ? "none" : "translateY(14px)",
        transition: `opacity 0.4s ease ${index * 50}ms, transform 0.4s ease ${index * 50}ms, box-shadow 0.2s ease, border-color 0.2s ease`,
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = `${meta.color}35`;
        (e.currentTarget as HTMLDivElement).style.boxShadow = `0 8px 32px rgba(0,0,0,0.15), 0 0 20px ${meta.glow}`;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = "";
        (e.currentTarget as HTMLDivElement).style.boxShadow = "";
      }}
    >
      {/* Card header */}
      <div className="mb-4 flex items-start justify-between gap-3">
        <div
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg transition-all"
          style={{
            background: `${meta.color}18`,
            border: `1px solid ${meta.color}30`,
            boxShadow: visible ? `0 0 12px ${meta.glow}` : "none",
          }}
        >
          <span
            className="material-symbols-outlined text-xl transition-all"
            style={{
              color: meta.color,
              filter: `drop-shadow(0 0 4px ${meta.glow})`,
            }}
          >
            smart_toy
          </span>
        </div>
        <span
          className="rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider"
          style={{
            color: meta.color,
            background: `${meta.color}14`,
            border: `1px solid ${meta.color}25`,
          }}
        >
          {meta.label}
        </span>
      </div>

      {/* Name & description */}
      <Link
        href={`/agents/${agent.id}`}
        className="mb-1 block text-base font-bold text-af-on-surface hover:text-af-primary transition-colors"
      >
        {agent.name}
      </Link>
      <p className="mb-4 flex-1 text-xs leading-relaxed text-af-muted line-clamp-2">
        {agent.description || "No description provided."}
      </p>

      {/* Health bar */}
      {health != null && (
        <div className="mb-4">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-af-muted-dim">Health</span>
            <span
              className="text-[11px] font-bold tabular-nums"
              style={{ color: healthColor(health) }}
            >
              {Math.round(health)}%
            </span>
          </div>
          <div className="h-1 w-full overflow-hidden rounded-full bg-af-border/30">
            <div
              className="h-full rounded-full transition-all duration-1000 ease-out"
              style={{
                width: visible ? `${health}%` : "0%",
                background: `linear-gradient(90deg, ${healthColor(health)}80, ${healthColor(health)})`,
                boxShadow: `0 0 6px ${healthColor(health)}50`,
              }}
            />
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-2 border-t border-af-border/30 pt-3">
        <button
          type="button"
          onClick={onChat}
          className="flex items-center gap-1 rounded-md border border-af-border/60 px-2.5 py-1 text-[11px] font-bold text-af-on-surface transition-colors hover:border-af-primary/60 hover:text-af-primary"
        >
          <span className="material-symbols-outlined text-sm">chat</span>
          Chat
        </button>
        <Link
          href={`/agents/${agent.id}/builder`}
          className="flex items-center gap-1 rounded-md border border-af-border/60 px-2.5 py-1 text-[11px] font-bold text-af-on-surface transition-colors hover:border-af-primary/60 hover:text-af-primary"
        >
          <span className="material-symbols-outlined text-sm">schema</span>
          Builder
        </Link>
        <button
          type="button"
          onClick={onExport}
          className="rounded-md border border-af-border/60 px-2.5 py-1 text-[11px] text-af-muted transition-colors hover:border-af-border hover:text-af-on-surface"
          title="Export JSON"
        >
          Export ↓
        </button>
        <button
          type="button"
          onClick={onCopySDK}
          className="rounded-md border border-af-border/60 px-2.5 py-1 text-[11px] text-af-muted transition-colors hover:border-af-tertiary/50 hover:text-af-tertiary"
          title="Copy Python SDK snippet"
        >
          {copiedId === agent.id ? "Copied!" : "SDK"}
        </button>
        <button
          type="button"
          onClick={onDelete}
          disabled={deletingId === agent.id}
          className="ml-auto rounded-md border border-transparent px-2.5 py-1 text-[11px] text-af-muted transition-colors hover:border-red-500/30 hover:text-red-400 disabled:opacity-50"
        >
          <span className="material-symbols-outlined text-sm">
            {deletingId === agent.id ? "hourglass_top" : "delete"}
          </span>
        </button>
      </div>
    </div>
  );
}

export default function AgentsPage() {
  const router = useRouter();
  const { openChat } = useChatContext();
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const importRef = useRef<HTMLInputElement>(null);

  async function handleExport(agentId: string, agentName: string) {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
    const resp = await fetch(`${API_BASE}/api/v1/agents/${agentId}/export?include_skills=true`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!resp.ok) { setError("Export failed"); return; }
    const bundle = await resp.json();
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${agentName.replace(/\s+/g, "-")}.json`;
    a.click();
    URL.revokeObjectURL(url);
    return bundle;
  }

  async function handleCopySDK(agentId: string, agentName: string) {
    try {
      const bundle = await handleExport(agentId, agentName);
      const snippet = bundle?.sdk_usage?.python ?? "";
      if (snippet) {
        await navigator.clipboard.writeText(snippet);
        setCopiedId(agentId);
        setTimeout(() => setCopiedId(null), 2000);
      }
    } catch { setError("Copy failed"); }
  }

  async function importAgent(file: File) {
    setImporting(true);
    setError(null);
    try {
      const raw = JSON.parse(await file.text());
      await api("/api/v1/agents/import", { method: "POST", body: JSON.stringify(raw) });
      const data = await api<Agent[]>("/api/v1/agents");
      setAgents(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    } finally { setImporting(false); }
  }

  async function deleteAgent(agentId: string, agentName: string) {
    if (!confirm(`Delete agent "${agentName}"? This action cannot be undone.`)) return;
    setDeletingId(agentId);
    setError(null);
    try {
      await api(`/api/v1/agents/${agentId}`, { method: "DELETE" });
      setAgents((prev) => prev?.filter((a) => a.id !== agentId) ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    } finally { setDeletingId(null); }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api<Agent[]>("/api/v1/agents");
        if (!cancelled) setAgents(data);
      } catch (e) {
        if (!cancelled) {
          if (e instanceof ApiError && e.status === 401) { router.push("/login"); return; }
          setError(e instanceof Error ? e.message : "Failed to load");
        }
      }
    })();
    return () => { cancelled = true; };
  }, [router]);

  const activeCount = agents?.filter((a) => /run|active/i.test(a.status)).length ?? 0;

  return (
    <ToolShell active="agents">
      <div className="mx-auto max-w-7xl pb-16">
        {/* Header */}
        <header className="mb-10">
          <div className="mb-2">
            <span className="af-kicker text-af-primary">[ AGENTS ]</span>
          </div>
          <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
            <h1 className="font-sans text-5xl font-bold tracking-tighter text-af-on-surface md:text-7xl">
              Your <span className="af-serif-italic text-af-primary">fleet</span>
            </h1>
            <div className="flex gap-3">
              <button
                type="button"
                disabled={importing}
                onClick={() => importRef.current?.click()}
                className="rounded-lg border border-af-border px-4 py-2 text-sm text-af-on-surface transition-colors hover:border-af-primary hover:text-af-primary disabled:opacity-50"
              >
                {importing ? "Importing…" : "Import JSON"}
              </button>
              <input
                ref={importRef}
                type="file"
                accept=".json"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void importAgent(f);
                  e.target.value = "";
                }}
              />
              <Link
                href="/agents/new"
                className="af-btn-primary inline-flex items-center gap-2 px-6 py-2.5 text-sm"
              >
                <span className="material-symbols-outlined text-sm">add</span>
                New agent
              </Link>
            </div>
          </div>
        </header>

        {/* Stats strip */}
        <div className="mb-10 grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            { label: "Total", value: agents?.length ?? "—", icon: "smart_toy", color: "#c3c0ff" },
            { label: "Active", value: agents ? activeCount : "—", icon: "play_circle", color: "#3cddc7" },
            { label: "Paused", value: agents ? (agents.length - activeCount) : "—", icon: "pause_circle", color: "#f59e0b" },
            { label: "Version", value: "v0.1", icon: "tag", color: "#a78bfa" },
          ].map(({ label, value, icon, color }) => (
            <div
              key={label}
              className="flex items-center gap-3 rounded-xl p-4"
              style={{
                background: "var(--af-glass-subtle)",
                backdropFilter: "blur(16px)",
                border: "1px solid var(--af-glass-border)",
              }}
            >
              <span
                className="material-symbols-outlined text-xl"
                style={{ color, filter: `drop-shadow(0 0 5px ${color}60)` }}
              >
                {icon}
              </span>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-af-muted-dim">{label}</div>
                <div className="text-xl font-bold tabular-nums text-af-on-surface">{String(value)}</div>
              </div>
            </div>
          ))}
        </div>

        {error && (
          <p className="mb-6 rounded-lg border border-af-error/30 bg-af-error/10 px-4 py-3 text-sm text-af-error">
            {error}
          </p>
        )}

        {/* Loading skeleton */}
        {!agents && !error && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="animate-pulse rounded-xl border border-af-border/30 bg-af-surface-container/40 p-5">
                <div className="mb-4 flex items-start gap-3">
                  <div className="h-11 w-11 rounded-lg bg-af-surface-high" />
                  <div className="ml-auto h-5 w-16 rounded-full bg-af-surface-high" />
                </div>
                <div className="mb-2 h-4 w-3/4 rounded bg-af-surface-high" />
                <div className="mb-4 h-3 w-full rounded bg-af-surface-high" />
                <div className="h-1 w-full rounded-full bg-af-surface-high" />
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {agents && agents.length === 0 && (
          <div className="flex min-h-[300px] flex-col items-center justify-center rounded-xl border border-dashed border-af-border/60 bg-af-surface-container/20 p-12 text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full border border-af-border bg-af-surface-container text-af-muted">
              <span className="material-symbols-outlined text-3xl">smart_toy</span>
            </div>
            <h3 className="mb-2 text-lg font-bold text-af-on-surface">No agents yet</h3>
            <p className="mb-6 max-w-sm text-sm text-af-muted">
              Get started by creating your first autonomous agent.
            </p>
            <Link href="/agents/new" className="af-btn-primary px-6 py-2.5 text-sm">
              Create your first agent
            </Link>
          </div>
        )}

        {/* Grid */}
        {agents && agents.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {agents.map((agent, i) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                index={i}
                copiedId={copiedId}
                deletingId={deletingId}
                onChat={() => openChat(agent.id)}
                onExport={() => void handleExport(agent.id, agent.name)}
                onCopySDK={() => void handleCopySDK(agent.id, agent.name)}
                onDelete={() => void deleteAgent(agent.id, agent.name)}
              />
            ))}
          </div>
        )}
      </div>
    </ToolShell>
  );
}
