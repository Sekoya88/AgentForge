"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  addEdge,
  Background,
  Controls,
  type Connection,
  type Edge,
  MiniMap,
  type Node,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ApiError, api } from "@/lib/api";

type NodeKind = "llm" | "tool" | "subagent" | "conditional" | "interrupt";

type Agent = {
  id: string;
  name: string;
  model_config: Record<string, unknown>;
  graph_definition: {
    nodes?: { id: string; type?: string; config?: Record<string, unknown> }[];
    edges?: { from: string; to: string; condition?: string | null }[];
    entry_point?: string;
  };
};

function newId() {
  return `n_${crypto.randomUUID().slice(0, 8)}`;
}

export default function AgentBuilderPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [agent, setAgent] = useState<Agent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [entryPoint, setEntryPoint] = useState("");
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [edgeConditionDraft, setEdgeConditionDraft] = useState("");

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const nodeIds = useMemo(() => nodes.map((n) => n.id), [nodes]);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const a = await api<Agent>(`/api/v1/agents/${id}`);
        if (!c) {
          setAgent(a);
          const gn = a.graph_definition.nodes ?? [];
          const ge = a.graph_definition.edges ?? [];
          const ep = a.graph_definition.entry_point ?? gn[0]?.id ?? "";
          setEntryPoint(ep);
          setNodes(
            gn.map((n, i) => ({
              id: n.id,
              position: { x: 80 + (i % 3) * 220, y: 80 + Math.floor(i / 3) * 140 },
              data: {
                label: `${n.type ?? "llm"} · ${n.id}`,
                nodeType: (n.type ?? "llm") as NodeKind,
              },
            })),
          );
          setEdges(
            ge.map((e, i) => ({
              id: `e_${i}_${e.from}_${e.to}`,
              source: e.from,
              target: e.to,
              data: { condition: e.condition ?? undefined },
              label: e.condition ? String(e.condition) : undefined,
            })),
          );
        }
      } catch (e) {
        if (!c) {
          if (e instanceof ApiError && e.status === 401) router.push("/login");
          else setError(e instanceof Error ? e.message : "Load failed");
        }
      }
    })();
    return () => {
      c = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- hydrate graph once per agent id
  }, [id, router]);

  const onConnect = useCallback(
    (p: Connection) =>
      setEdges((eds) =>
        addEdge(
          {
            ...p,
            id: `e_${p.source}_${p.target}_${eds.length}`,
            data: {},
          },
          eds,
        ),
      ),
    [setEdges],
  );

  const addPaletteNode = useCallback(
    (kind: NodeKind) => {
      const nid = newId();
      setNodes((prev) => [
        ...prev,
        {
          id: nid,
          position: { x: 120 + prev.length * 30, y: 120 + prev.length * 20 },
          data: { label: `${kind} · ${nid}`, nodeType: kind },
        },
      ]);
      if (!entryPoint) setEntryPoint(nid);
    },
    [entryPoint, setNodes],
  );

  useEffect(() => {
    if (!selectedEdgeId) {
      setEdgeConditionDraft("");
      return;
    }
    const e = edges.find((x) => x.id === selectedEdgeId);
    setEdgeConditionDraft(
      e?.data && typeof e.data === "object" && "condition" in e.data
        ? String((e.data as { condition?: string }).condition ?? "")
        : "",
    );
  }, [selectedEdgeId, edges]);

  function applyEdgeCondition() {
    if (!selectedEdgeId) return;
    setEdges((eds) =>
      eds.map((e) => {
        if (e.id !== selectedEdgeId) return e;
        const cond = edgeConditionDraft.trim() || undefined;
        return {
          ...e,
          data: { ...e.data, condition: cond },
          label: cond,
        };
      }),
    );
  }

  function buildGraphDefinition() {
    const gn = nodes.map((n) => {
      const nt = (n.data as { nodeType?: NodeKind }).nodeType ?? "llm";
      return { id: n.id, type: nt, config: {} };
    });
    const ge = edges.map((e) => ({
      from: e.source,
      to: e.target,
      condition:
        e.data && typeof e.data === "object" && "condition" in e.data
          ? ((e.data as { condition?: string | null }).condition ?? null)
          : null,
    }));
    const ep = entryPoint && nodeIds.includes(entryPoint) ? entryPoint : nodeIds[0] ?? "";
    return { nodes: gn, edges: ge, entry_point: ep };
  }

  async function saveGraph() {
    if (!agent) return;
    setBusy(true);
    setSaveMsg(null);
    setError(null);
    try {
      const graph_definition = buildGraphDefinition();
      await api(`/api/v1/agents/${id}`, {
        method: "PUT",
        body: JSON.stringify({
          graph_definition,
          model_config: agent.model_config,
        }),
      });
      setSaveMsg("Saved.");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  if (error && !agent) return <p className="text-red-400">{error}</p>;
  if (!agent) return <p className="text-neutral-500">Loading…</p>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <Link href={`/agents/${id}`} className="text-sm text-neutral-500 hover:text-white">
          ← {agent.name}
        </Link>
      </div>
      <h1 className="text-xl font-semibold">Visual builder</h1>
      <p className="text-sm text-neutral-500">
        Add nodes, connect edges, set optional <strong>condition</strong> strings (matched as substring
        in the last AI message for branching). Choose entry point, then save.
      </p>

      <div className="flex flex-wrap gap-2">
        {(
          [
            ["llm", "LLM"],
            ["tool", "Tool"],
            ["subagent", "Subagent"],
            ["conditional", "Router"],
            ["interrupt", "Interrupt (HITL)"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            type="button"
            onClick={() => addPaletteNode(k)}
            className="rounded-md border border-neutral-600 px-2 py-1 text-xs text-neutral-200 hover:border-cyan-600"
          >
            + {label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label className="block text-xs text-neutral-500">Entry point</label>
          <select
            value={entryPoint}
            onChange={(e) => setEntryPoint(e.target.value)}
            className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm"
          >
            {nodeIds.map((nid) => (
              <option key={nid} value={nid}>
                {nid}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          disabled={busy || nodeIds.length === 0}
          onClick={saveGraph}
          className="rounded-md bg-cyan-500 px-4 py-2 text-sm font-medium text-black disabled:opacity-50"
        >
          {busy ? "Saving…" : "Save graph"}
        </button>
        {saveMsg && <span className="text-sm text-green-400">{saveMsg}</span>}
      </div>

      {selectedEdgeId && (
        <div className="flex flex-wrap items-end gap-2 rounded-md border border-neutral-800 bg-neutral-900/80 p-3">
          <div>
            <label className="block text-xs text-neutral-500">Edge condition (optional)</label>
            <input
              value={edgeConditionDraft}
              onChange={(e) => setEdgeConditionDraft(e.target.value)}
              placeholder="e.g. approved — substring match on last AI output"
              className="w-72 max-w-full rounded-md border border-neutral-700 bg-neutral-950 px-2 py-1 text-sm"
            />
          </div>
          <button
            type="button"
            onClick={applyEdgeCondition}
            className="rounded-md border border-neutral-600 px-3 py-1 text-sm"
          >
            Apply to selected edge
          </button>
          <button
            type="button"
            onClick={() => setSelectedEdgeId(null)}
            className="text-sm text-neutral-500 hover:text-white"
          >
            Clear selection
          </button>
        </div>
      )}

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="h-[520px] w-full rounded-lg border border-neutral-800 bg-neutral-950">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onEdgeClick={(_, edge) => setSelectedEdgeId(edge.id)}
          fitView
        >
          <Background />
          <Controls />
          <MiniMap />
        </ReactFlow>
      </div>
    </div>
  );
}
