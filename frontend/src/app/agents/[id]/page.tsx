"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { ExecutionLog } from "@/components/execution/ExecutionLog";
import { InterruptModal } from "@/components/execution/InterruptModal";
import { ApiError, api } from "@/lib/api";
import { consumeExecutionSse } from "@/lib/sse";
import { ChatUI } from "@/components/chat/ChatUI";
type Agent = {
  id: string;
  name: string;
  graph_definition: Record<string, unknown>;
  model_config: Record<string, unknown>;
  skills: string[];
  security_score: number | null;
};

type SkillRow = { id: string; name: string };

type Execution = {
  id: string;
  status: string;
  output_messages: unknown[] | null;
  duration_ms: number | null;
};

type LogLine = { event: string; data: string; at: number };

type CampaignHistoryRow = {
  id: string;
  status: string;
  overall_score: number | null;
  total_tests: number | null;
  created_at: string;
  completed_at: string | null;
};

type AgentVersionRow = {
  id: string;
  version_number: number;
  graph_definition: Record<string, unknown>;
  llm_model_config: Record<string, unknown>;
  skills: string[];
  change_note: string | null;
  created_at: string;
};

export default function AgentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [agent, setAgent] = useState<Agent | null>(null);
  const [lastExec, setLastExec] = useState<Execution | null>(null);
  const [streamLines, setStreamLines] = useState<LogLine[]>([]);
  const [input, setInput] = useState("Hello");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [campaignBusy, setCampaignBusy] = useState(false);
  const [useStream, setUseStream] = useState(true);
  const [registrySkills, setRegistrySkills] = useState<SkillRow[]>([]);
  const [skillPick, setSkillPick] = useState<Set<string>>(new Set());
  const [skillsBusy, setSkillsBusy] = useState(false);
  const [campaignHistory, setCampaignHistory] = useState<CampaignHistoryRow[]>([]);
  const [versions, setVersions] = useState<AgentVersionRow[]>([]);
  const [rollbackBusy, setRollbackBusy] = useState(false);
  const [expandedVersion, setExpandedVersion] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  type PendingTool = { tool_name: string; arg: string };
  const [interruptState, setInterruptState] = useState<{
    executionId: string;
    pendingTools: PendingTool[];
  } | null>(null);


  async function loadCampaignHistory() {
    try {
      const camps = await api<CampaignHistoryRow[]>(
        `/api/v1/campaigns?agent_id=${encodeURIComponent(id)}`,
      );
      setCampaignHistory(camps);
    } catch {
      setCampaignHistory([]);
    }
  }

  const scoreDelta = useMemo(() => {
    const scored = campaignHistory.filter(
      (row) => row.overall_score != null && /complete/i.test(row.status),
    );
    if (scored.length < 2) return null;
    const [latest, prev] = scored;
    if (latest.overall_score == null || prev.overall_score == null) return null;
    return latest.overall_score - prev.overall_score;
  }, [campaignHistory]);

  useEffect(() => {
    let c = false;
    setCampaignHistory([]);
    (async () => {
      try {
        const a = await api<Agent>(`/api/v1/agents/${id}`);
        if (!c) {
          setAgent(a);
          setSkillPick(new Set(a.skills ?? []));
        }
      } catch (e) {
        if (!c) {
          if (e instanceof ApiError && e.status === 401) router.push("/login");
          else setError(e instanceof Error ? e.message : "Load failed");
        }
        return;
      }
      try {
        const [camps, vers] = await Promise.allSettled([
          api<CampaignHistoryRow[]>(`/api/v1/campaigns?agent_id=${encodeURIComponent(id)}`),
          api<AgentVersionRow[]>(`/api/v1/agents/${id}/versions`),
        ]);
        if (!c) {
          setCampaignHistory(camps.status === "fulfilled" ? camps.value : []);
          setVersions(vers.status === "fulfilled" ? vers.value : []);
        }
      } catch {
        if (!c) { setCampaignHistory([]); setVersions([]); }
      }
    })();
    return () => {
      c = true;
      abortRef.current?.abort();
    };
  }, [id, router]);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const rows = await api<SkillRow[]>("/api/v1/skills");
        if (!c) setRegistrySkills(rows);
      } catch {
        /* skills optional */
      }
    })();
    return () => {
      c = true;
    };
  }, []);

  async function saveAttachedSkills() {
    setSkillsBusy(true);
    setError(null);
    try {
      const a = await api<Agent>(`/api/v1/agents/${id}`, {
        method: "PUT",
        body: JSON.stringify({ skills: [...skillPick] }),
      });
      setAgent(a);
      setSkillPick(new Set(a.skills ?? []));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save skills failed");
    } finally {
      setSkillsBusy(false);
    }
  }

  function toggleSkill(sid: string) {
    setSkillPick((prev) => {
      const next = new Set(prev);
      if (next.has(sid)) next.delete(sid);
      else next.add(sid);
      return next;
    });
  }

  async function run() {
    setBusy(true);
    setError(null);
    setStreamLines([]);
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    const signal = abortRef.current.signal;

    try {
      if (useStream) {
        const ex = await api<Execution>(`/api/v1/agents/${id}/execute`, {
          method: "POST",
          body: JSON.stringify({
            input_messages: [{ role: "user", content: input }],
            run_async: true,
          }),
        });
        if (ex.status !== "running") {
          setLastExec(ex);
          setBusy(false);
          return;
        }
        const lines: LogLine[] = [];
        await consumeExecutionSse(
          id,
          ex.id,
          (event, dataJson) => {
            lines.push({ event, data: dataJson, at: Date.now() });
            setStreamLines([...lines]);
            if (event === "interrupt") {
              try {
                const parsed = JSON.parse(dataJson);
                // Backend emits {node_id, allowed_decisions}
                const nodeId = parsed?.node_id ?? "unknown";
                const pending: PendingTool[] = parsed?.interrupt_state?.pending_tools
                  ?? [{ tool_name: nodeId, arg: JSON.stringify(parsed) }];
                setInterruptState({ executionId: ex.id, pendingTools: pending });
              } catch {
                /* ignore parse errors */
              }
            }
          },
          signal,
        );
        const final = await api<Execution>(`/api/v1/agents/${id}/executions/${ex.id}`);
        setLastExec(final);
      } else {
        const ex = await api<Execution>(`/api/v1/agents/${id}/execute`, {
          method: "POST",
          body: JSON.stringify({
            input_messages: [{ role: "user", content: input }],
            run_async: false,
          }),
        });
        setLastExec(ex);
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setError(e instanceof Error ? e.message : "Execute failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleInterruptDecision(
    decisions: { tool_name: string; decision: "approve" | "reject"; arg?: string }[],
  ) {
    if (!interruptState) return;
    const { executionId } = interruptState;
    setInterruptState(null);
    setBusy(true);
    setError(null);
    try {
      await api(`/api/v1/agents/${id}/executions/${executionId}/interrupt`, {
        method: "POST",
        body: JSON.stringify({ decisions }),
      });
      // Re-open SSE stream to watch resumed execution
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      const signal = abortRef.current.signal;
      const lines: LogLine[] = [...streamLines];
      await consumeExecutionSse(
        id,
        executionId,
        (event, dataJson) => {
          lines.push({ event, data: dataJson, at: Date.now() });
          setStreamLines([...lines]);
          if (event === "interrupt") {
            try {
              const parsed = JSON.parse(dataJson);
              const nodeId = parsed?.node_id ?? "unknown";
              const pending: PendingTool[] = parsed?.interrupt_state?.pending_tools
                ?? [{ tool_name: nodeId, arg: JSON.stringify(parsed) }];
              setInterruptState({ executionId, pendingTools: pending });
            } catch {
              /* ignore */
            }
          }
        },
        signal,
      );
      const final = await api<Execution>(`/api/v1/agents/${id}/executions/${executionId}`);
      setLastExec(final);
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setError(e instanceof Error ? e.message : "Resume failed");
      }
    } finally {
      setBusy(false);
    }
  }

  function handleInterruptCancel() {
    setInterruptState(null);
    setBusy(false);
    abortRef.current?.abort();
  }

  async function rollbackToVersion(versionNumber: number) {
    setRollbackBusy(true);
    setError(null);
    try {
      const a = await api<Agent>(`/api/v1/agents/${id}/rollback/${versionNumber}`, { method: "POST" });
      setAgent(a);
      const vers = await api<AgentVersionRow[]>(`/api/v1/agents/${id}/versions`);
      setVersions(vers);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Rollback failed");
    } finally {
      setRollbackBusy(false);
    }
  }

  async function runCampaign() {
    setCampaignBusy(true);
    setError(null);
    try {
      await api(`/api/v1/campaigns`, {
        method: "POST",
        body: JSON.stringify({
          agent_id: id,
          plugins: ["default"],
          strategies: ["basic"],
          run_async: false,
        }),
      });
      const a = await api<Agent>(`/api/v1/agents/${id}`);
      setAgent(a);
      await loadCampaignHistory();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Campaign failed");
    } finally {
      setCampaignBusy(false);
    }
  }

  const [deleteBusy, setDeleteBusy] = useState(false);

  async function deleteAgent() {
    if (!confirm("Delete this agent permanently? This cannot be undone.")) return;
    setDeleteBusy(true);
    try {
      await api(`/api/v1/agents/${id}`, { method: "DELETE" });
      router.push("/agents");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
      setDeleteBusy(false);
    }
  }

  async function exportAgent() {
    try {
      const data = await api(`/api/v1/agents/${id}/export`);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${agent?.name ?? "agent"}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    }
  }

  if (error && !agent) return <p className="px-4 text-af-error">{error}</p>;
  if (!agent) return <p className="px-4 text-af-muted">Loading…</p>;

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-8 md:px-8">
      <Link href="/agents" className="text-sm text-af-muted hover:text-af-primary">
        ← Agents
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <span className="af-kicker text-af-primary">[ AGENT ]</span>
          <h1 className="mt-2 font-sans text-3xl font-bold text-white">{agent.name}</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/agents/${id}/builder`}
            className="rounded-lg border border-af-border px-4 py-2 text-sm text-af-on-surface transition-colors hover:border-af-primary hover:text-af-primary"
          >
            Open builder
          </Link>
          <button
            type="button"
            onClick={exportAgent}
            className="rounded-lg border border-af-border px-4 py-2 text-sm text-af-on-surface transition-colors hover:border-af-primary hover:text-af-primary"
          >
            Export JSON
          </button>
          <button
            type="button"
            onClick={runCampaign}
            disabled={campaignBusy}
            className="rounded-lg border border-af-secondary/40 bg-af-secondary/10 px-4 py-2 text-sm font-bold text-af-secondary transition-all hover:bg-af-secondary/20 flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {campaignBusy ? (
              <>
                <span className="material-symbols-outlined animate-spin text-sm">autorenew</span>
                Red-team…
              </>
            ) : (
              "Run red-team"
            )}
          </button>
          <button
            type="button"
            onClick={deleteAgent}
            disabled={deleteBusy}
            className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-400 transition-colors hover:bg-red-500/20 disabled:opacity-50"
          >
            Delete
          </button>
        </div>
      </div>
      {agent.security_score != null && (
        <p className="text-sm text-af-muted">
          Security score: <span className="text-af-tertiary">{agent.security_score}</span>{" "}
          <span className="text-af-muted-dim">(latest campaign)</span>
        </p>
      )}
      <div className="af-card space-y-3 p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
            Red-team history
          </p>
          {scoreDelta != null && (
            <span className="text-xs text-af-muted">
              Δ vs previous:{" "}
              <span className={scoreDelta >= 0 ? "text-af-tertiary" : "text-af-error"}>
                {scoreDelta >= 0 ? "+" : ""}
                {scoreDelta.toFixed(1)}
              </span>
            </span>
          )}
        </div>
        {campaignHistory.length === 0 ? (
          <p className="text-sm text-af-muted">No campaigns for this agent yet.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {campaignHistory.slice(0, 10).map((row) => (
              <li
                key={row.id}
                className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 py-2 last:border-0"
              >
                <span className="font-mono text-xs text-af-muted-dim">{row.id.slice(0, 8)}…</span>
                <span className="text-af-muted">{row.status}</span>
                <span className="min-w-[3rem] text-af-tertiary">
                  {row.overall_score != null ? row.overall_score : "—"}
                </span>
                <Link
                  href={`/campaigns/${row.id}`}
                  className="text-xs text-af-primary hover:underline"
                >
                  report
                </Link>
              </li>
            ))}
          </ul>
        )}
        <Link href="/campaigns" className="inline-block text-xs text-af-muted hover:text-af-primary">
          All campaigns →
        </Link>
      </div>
      <div className="af-card space-y-4 p-6">
        <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
          Attached skills (registry)
        </p>
        <p className="text-xs text-af-muted">
          Tool nodes use <span className="font-mono text-af-muted-dim">config.tool_name</span> equal
          to the skill&apos;s <span className="font-mono text-af-muted-dim">name</span> (registry).
        </p>
        {registrySkills.length === 0 ? (
          <p className="text-sm text-af-muted">
            No skills yet —{" "}
            <Link href="/skills/new" className="text-af-primary hover:underline">
              create one
            </Link>
            .
          </p>
        ) : (
          <ul className="max-h-48 space-y-2 overflow-y-auto text-sm">
            {registrySkills.map((s) => (
              <li key={s.id} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id={`sk-${s.id}`}
                  checked={skillPick.has(s.id)}
                  onChange={() => toggleSkill(s.id)}
                  className="rounded border-af-border"
                />
                <label htmlFor={`sk-${s.id}`} className="cursor-pointer font-mono text-af-muted">
                  {s.name}{" "}
                  <span className="text-af-muted-dim text-xs">({s.id.slice(0, 8)}…)</span>
                </label>
              </li>
            ))}
          </ul>
        )}
        <button
          type="button"
          onClick={saveAttachedSkills}
          disabled={skillsBusy}
          className="rounded-lg border border-af-primary/40 bg-af-primary/10 px-4 py-2 text-sm text-af-primary transition-colors hover:bg-af-primary/20 flex items-center gap-2 disabled:opacity-50"
        >
          {skillsBusy ? (
            <>
              <span className="material-symbols-outlined animate-spin text-sm">autorenew</span>
              Saving…
            </>
          ) : (
            "Save skills"
          )}
        </button>
      </div>
      <div className="af-card space-y-4 p-6">
        <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">model_config</p>
        <pre className="overflow-x-auto text-xs text-af-muted">
          {JSON.stringify(agent.model_config, null, 2)}
        </pre>
      </div>
      {/* ── Version History ── */}
      <div className="af-card space-y-3 p-6">
        <div className="flex items-center justify-between">
          <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
            Version history
          </p>
          <span className="text-xs text-af-muted">{versions.length} snapshot{versions.length !== 1 ? "s" : ""}</span>
        </div>
        {versions.length === 0 ? (
          <p className="text-sm text-af-muted">No versions yet — snapshots are created on every save.</p>
        ) : (
          <ul className="space-y-2">
            {versions.map((v, i) => (
              <li key={v.id} className="rounded-lg border border-af-border/30 bg-af-surface-container/30">
                <div
                  className="flex cursor-pointer flex-wrap items-center justify-between gap-2 px-4 py-3"
                  onClick={() => setExpandedVersion(expandedVersion === v.version_number ? null : v.version_number)}
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs font-bold text-af-primary">v{v.version_number}</span>
                    {i === 0 && (
                      <span className="rounded border border-af-tertiary/30 bg-af-tertiary/10 px-1.5 py-0.5 text-[10px] font-bold uppercase text-af-tertiary">
                        current
                      </span>
                    )}
                    {v.change_note && (
                      <span className="text-xs text-af-muted">{v.change_note}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs text-af-muted-dim">
                      {new Date(v.created_at).toLocaleString()}
                    </span>
                    {i !== 0 && (
                      <button
                        type="button"
                        disabled={rollbackBusy}
                        onClick={(e) => { e.stopPropagation(); void rollbackToVersion(v.version_number); }}
                        className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold uppercase text-amber-400 transition-colors hover:bg-amber-500/20 disabled:opacity-50"
                      >
                        Rollback
                      </button>
                    )}
                    <span className="material-symbols-outlined text-sm text-af-muted-dim">
                      {expandedVersion === v.version_number ? "expand_less" : "expand_more"}
                    </span>
                  </div>
                </div>
                {expandedVersion === v.version_number && (
                  <div className="border-t border-af-border/20 px-4 py-3">
                    <p className="mb-1 text-[10px] uppercase tracking-wider text-af-muted-dim">graph_definition</p>
                    <pre className="overflow-x-auto rounded bg-black/20 p-3 text-xs text-af-muted">
                      {JSON.stringify(v.graph_definition, null, 2)}
                    </pre>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="af-card space-y-4 p-6">
        <label className="flex items-center gap-2 text-sm text-af-muted">
          <input
            type="checkbox"
            checked={useStream}
            onChange={(e) => setUseStream(e.target.checked)}
            className="rounded border-af-border"
          />
          Stream logs (async + SSE, needs Redis)
        </label>
        <label className="block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
          User message
        </label>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="af-input max-w-lg"
        />
        <button
          type="button"
          onClick={run}
          disabled={busy || !input.trim()}
          className="af-btn-primary flex items-center justify-center gap-2 px-6 py-2 text-sm disabled:opacity-50"
        >
          {busy ? (
            <>
              <span className="material-symbols-outlined animate-spin text-sm">autorenew</span>
              Running…
            </>
          ) : (
            "Execute"
          )}
        </button>
      </div>
      {error && <p className="text-sm text-af-error">{error}</p>}
      <ExecutionLog lines={streamLines} />
      {lastExec && (
        <div className="af-card p-6">
          <div className="mb-6 flex items-center justify-between">
            <h3 className="font-bold text-white">Execution Result</h3>
            <span className="text-xs text-af-muted">
              Status: {lastExec.status} · {lastExec.duration_ms ?? "?"} ms
            </span>
          </div>
          <ChatUI
            messages={
              (lastExec.output_messages as {
                role: "user" | "assistant" | "system" | "tool";
                content: string;
              }[]) || []
            }
          />
        </div>
      )}
      {interruptState && (
        <InterruptModal
          executionId={interruptState.executionId}
          pendingTools={interruptState.pendingTools}
          onDecided={handleInterruptDecision}
          onCancel={handleInterruptCancel}
        />
      )}
    </div>
  );
}
