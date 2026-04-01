"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
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
  Handle,
  Position,
  useReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ApiError, api } from "@/lib/api";

type NodeKind =
  | "llm"
  | "tool"
  | "subagent"
  | "conditional"
  | "interrupt"
  | "asr"
  | "tts";

type GraphQuickstart = {
  label: string;
  icon: string;
  description: string;
  nodes: { id: string; type: NodeKind; config: Record<string, unknown> }[];
  edges: { from: string; to: string; condition?: string }[];
  entry: string;
};

const GRAPH_QUICKSTARTS: GraphQuickstart[] = [
  {
    label: "Chat Simple",
    icon: "💬",
    description: "Un agent conversationnel avec un rôle défini",
    nodes: [
      {
        id: "n_llm",
        type: "llm",
        config: {
          prompt:
            "Tu es un assistant utile et précis. Réponds de façon concise et dans la langue de l'utilisateur.",
        },
      },
    ],
    edges: [],
    entry: "n_llm",
  },
  {
    label: "Agent avec Outil",
    icon: "🔧",
    description: "LLM qui peut appeler un outil puis répondre",
    nodes: [
      {
        id: "n_tool",
        type: "tool",
        config: { tool_name: "" },
      },
      {
        id: "n_llm",
        type: "llm",
        config: {
          prompt: "Utilise les résultats de l'outil pour répondre à l'utilisateur.",
        },
      },
    ],
    edges: [{ from: "n_tool", to: "n_llm" }],
    entry: "n_tool",
  },
  {
    label: "Pipeline",
    icon: "⚡",
    description: "Enchaînement de traitements séquentiels",
    nodes: [
      {
        id: "n_llm1",
        type: "llm",
        config: {
          prompt: "Analyse et structure la demande de l'utilisateur.",
        },
      },
      {
        id: "n_tool",
        type: "tool",
        config: { tool_name: "" },
      },
      {
        id: "n_llm2",
        type: "llm",
        config: {
          prompt: "Synthétise les résultats et présente une réponse claire.",
        },
      },
    ],
    edges: [{ from: "n_llm1", to: "n_tool" }, { from: "n_tool", to: "n_llm2" }],
    entry: "n_llm1",
  },
];

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

type DeployedSpeechJob = {
  id: string;
  modality: string;
  inference_endpoint: string | null;
};

const DeployedSpeechContext = createContext<DeployedSpeechJob[]>([]);

function newId() {
  return `n_${crypto.randomUUID().slice(0, 8)}`;
}

import type { NodeProps } from "@xyflow/react";

function CustomNode({ id, data, isConnectable }: NodeProps) {
  const { setNodes } = useReactFlow();
  const deployedSpeech = useContext(DeployedSpeechContext);
  const { nodeType, config } = data as { nodeType: string; config: Record<string, unknown> };

  const updateConfig = (key: string, value: string) => {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id === id) {
          return {
            ...n,
            data: {
              ...n.data,
              config: { ...(n.data.config as Record<string, unknown>), [key]: value },
            },
          };
        }
        return n;
      }),
    );
  };

  return (
    <div className="af-card min-w-[240px] border-af-border bg-af-surface-container/95 p-4 shadow-xl backdrop-blur-sm">
      <Handle
        type="target"
        position={Position.Top}
        isConnectable={isConnectable}
        className="!h-3 !w-3 !bg-af-primary !border-af-surface-void"
      />
      <div className="mb-3 flex items-center justify-between border-b border-white/10 pb-2">
        <span className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
          {String(nodeType)}
        </span>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-af-muted">{id}</span>
          <button
            type="button"
            onClick={() => setNodes((nds) => nds.filter((n) => n.id !== id))}
            className="nodrag text-[10px] text-af-muted hover:text-red-400 transition-colors leading-none"
            title="Supprimer ce nœud"
          >
            ✕
          </button>
        </div>
      </div>

      {nodeType === "llm" && (
        <div className="space-y-2">
          <label className="text-[10px] uppercase text-af-muted-dim">
            System Prompt
          </label>
          <textarea
            value={(config?.prompt as string) || ""}
            onChange={(e) => updateConfig("prompt", e.target.value)}
            placeholder={`Décris le rôle et comportement de l'agent...\n\nExemple : "Tu es un assistant spécialisé en finance. Tu réponds toujours en français, de façon concise, en citant des chiffres précis si disponibles."`}
            className="af-input nodrag min-h-[80px] p-2 text-xs"
          />
        </div>
      )}

      {nodeType === "tool" && (
        <div className="space-y-2">
          <label className="text-[10px] uppercase text-af-muted-dim">
            Tool Name
          </label>
          <input
            value={(config?.tool_name as string) || ""}
            onChange={(e) => updateConfig("tool_name", e.target.value)}
            placeholder="e.g. echo"
            className="af-input nodrag p-2 text-xs"
          />
        </div>
      )}

      {nodeType === "subagent" && (
        <div className="space-y-2">
          <label className="text-[10px] uppercase text-af-muted-dim">
            Subagent ID
          </label>
          <input
            value={(config?.subagent_id as string) || ""}
            onChange={(e) => updateConfig("subagent_id", e.target.value)}
            placeholder="Agent UUID"
            className="af-input nodrag p-2 text-xs"
          />
        </div>
      )}

      {nodeType === "conditional" && (
        <div className="text-xs text-af-muted">
          Routes based on edge conditions.
        </div>
      )}
      {nodeType === "interrupt" && (
        <div className="text-xs text-af-muted">
          Pauses for human-in-the-loop.
        </div>
      )}

      {nodeType === "asr" && (
        <div className="space-y-2">
          <label className="text-[10px] uppercase text-af-muted-dim">Provider</label>
          <select
            value={(config?.provider as string) || "openai_whisper"}
            onChange={(e) => updateConfig("provider", e.target.value)}
            className="af-input nodrag p-2 text-xs"
          >
            <option value="openai_whisper">OpenAI Whisper</option>
            <option value="finetuned_whisper">Fine-tuned (HTTP / Modal)</option>
          </select>
          {(config?.provider as string) === "finetuned_whisper" ? (
            <>
              <label className="text-[10px] uppercase text-af-muted-dim">
                Deployed job (sets job id; URL resolved at run)
              </label>
              <select
                value={(config?.finetune_job_id as string) || ""}
                onChange={(e) => {
                  const v = e.target.value;
                  updateConfig("finetune_job_id", v);
                  if (v) updateConfig("endpoint_url", "");
                }}
                className="af-input nodrag p-2 text-xs"
              >
                <option value="">— manual below —</option>
                {deployedSpeech
                  .filter((j) => j.modality === "whisper" && j.inference_endpoint)
                  .map((j) => (
                    <option key={j.id} value={j.id}>
                      {j.id.slice(0, 8)}…
                    </option>
                  ))}
              </select>
              <label className="text-[10px] uppercase text-af-muted-dim">
                Inference URL (optional override)
              </label>
              <input
                value={(config?.endpoint_url as string) || ""}
                onChange={(e) => updateConfig("endpoint_url", e.target.value)}
                placeholder="https://…modal.run/transcribe"
                className="af-input nodrag p-2 text-xs font-mono"
              />
              <label className="text-[10px] uppercase text-af-muted-dim">
                Finetune job ID (manual)
              </label>
              <input
                value={(config?.finetune_job_id as string) || ""}
                onChange={(e) => updateConfig("finetune_job_id", e.target.value)}
                placeholder="UUID"
                className="af-input nodrag p-2 text-xs font-mono"
              />
            </>
          ) : (
            <>
              <label className="text-[10px] uppercase text-af-muted-dim">
                Language (optional)
              </label>
              <input
                value={(config?.language as string) || ""}
                onChange={(e) => updateConfig("language", e.target.value)}
                placeholder="e.g. fr, en"
                className="af-input nodrag p-2 text-xs"
              />
            </>
          )}
        </div>
      )}
      {nodeType === "tts" && (
        <div className="space-y-2">
          <label className="text-[10px] uppercase text-af-muted-dim">Provider</label>
          <select
            value={(config?.provider as string) || "openai_tts"}
            onChange={(e) => updateConfig("provider", e.target.value)}
            className="af-input nodrag p-2 text-xs"
          >
            <option value="openai_tts">OpenAI TTS</option>
            <option value="elevenlabs">ElevenLabs</option>
            <option value="finetuned_tts">Fine-tuned voice (HTTP / Modal)</option>
          </select>
          {(config?.provider as string) === "finetuned_tts" ? (
            <>
              <label className="text-[10px] uppercase text-af-muted-dim">
                Deployed TTS job
              </label>
              <select
                value={(config?.finetune_job_id as string) || ""}
                onChange={(e) => {
                  const v = e.target.value;
                  updateConfig("finetune_job_id", v);
                  if (v) updateConfig("endpoint_url", "");
                }}
                className="af-input nodrag p-2 text-xs"
              >
                <option value="">— manual below —</option>
                {deployedSpeech
                  .filter((j) => j.modality === "tts_voice" && j.inference_endpoint)
                  .map((j) => (
                    <option key={j.id} value={j.id}>
                      {j.id.slice(0, 8)}…
                    </option>
                  ))}
              </select>
              <label className="text-[10px] uppercase text-af-muted-dim">
                Inference URL (optional override)
              </label>
              <input
                value={(config?.endpoint_url as string) || ""}
                onChange={(e) => updateConfig("endpoint_url", e.target.value)}
                placeholder="https://…modal.run/synthesize"
                className="af-input nodrag p-2 text-xs font-mono"
              />
              <label className="text-[10px] uppercase text-af-muted-dim">
                Finetune job ID (manual)
              </label>
              <input
                value={(config?.finetune_job_id as string) || ""}
                onChange={(e) => updateConfig("finetune_job_id", e.target.value)}
                placeholder="UUID"
                className="af-input nodrag p-2 text-xs font-mono"
              />
              <label className="text-[10px] uppercase text-af-muted-dim">
                Voice ID
              </label>
              <input
                value={(config?.voice_id as string) || ""}
                onChange={(e) => updateConfig("voice_id", e.target.value)}
                placeholder="Deployed voice / model id"
                className="af-input nodrag p-2 text-xs font-mono"
              />
            </>
          ) : (config?.provider as string) === "elevenlabs" ? (
            <>
              <label className="text-[10px] uppercase text-af-muted-dim">
                Voice ID
              </label>
              <input
                value={(config?.voice as string) || ""}
                onChange={(e) => updateConfig("voice", e.target.value)}
                placeholder="ElevenLabs voice id"
                className="af-input nodrag p-2 text-xs"
              />
            </>
          ) : (
            <>
              <label className="text-[10px] uppercase text-af-muted-dim">Voice</label>
              <select
                value={(config?.voice as string) || "nova"}
                onChange={(e) => updateConfig("voice", e.target.value)}
                className="af-input nodrag p-2 text-xs"
              >
                {["alloy", "echo", "fable", "onyx", "nova", "shimmer"].map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </>
          )}
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        isConnectable={isConnectable}
        className="!h-3 !w-3 !bg-af-primary !border-af-surface-void"
      />
    </div>
  );
}

const nodeTypes = {
  af_node: CustomNode,
};

function BuilderInner() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [agent, setAgent] = useState<Agent | null>(null);
  const [deployedSpeech, setDeployedSpeech] = useState<DeployedSpeechJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [entryPoint, setEntryPoint] = useState("");
  const [modelConfig, setModelConfig] = useState<{
    provider: string;
    model: string;
    temperature: number;
  }>({
    provider: "openai",
    model: "gpt-5.4-mini",
    temperature: 0.7,
  });
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [edgeConditionDraft, setEdgeConditionDraft] = useState("");

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [showTemplateOverlay, setShowTemplateOverlay] = useState(false);

  const nodeIds = useMemo(() => nodes.map((n) => n.id), [nodes]);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const a = await api<Agent>(`/api/v1/agents/${id}`);
        if (!c) {
          setAgent(a);
          setModelConfig({
            provider: (a.model_config?.provider as string) || "openai",
            model: (a.model_config?.model as string) || "gpt-5.4-mini",
            temperature: (a.model_config?.temperature as number) ?? 0.7,
          });
          const gn = a.graph_definition.nodes ?? [];
          const ge = a.graph_definition.edges ?? [];
          const ep = a.graph_definition.entry_point ?? gn[0]?.id ?? "";
          setEntryPoint(ep);
          if (gn.length === 0) setShowTemplateOverlay(true);
          setNodes(
            gn.map((n, i) => ({
              id: n.id,
              type: "af_node",
              position: {
                x: 80 + (i % 3) * 320,
                y: 80 + Math.floor(i / 3) * 200,
              },
              data: {
                nodeType: (n.type ?? "llm") as NodeKind,
                config: n.config ?? {},
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
              style: { stroke: "#c3c0ff", strokeWidth: 2 },
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
  }, [id, router, setNodes, setEdges]);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const jobs = await api<DeployedSpeechJob[]>("/api/v1/speech/deployed");
        if (!c) setDeployedSpeech(jobs);
      } catch {
        if (!c) setDeployedSpeech([]);
      }
    })();
    return () => {
      c = true;
    };
  }, []);

  const onConnect = useCallback(
    (p: Connection) =>
      setEdges((eds) =>
        addEdge(
          {
            ...p,
            id: `e_${p.source}_${p.target}_${eds.length}`,
            data: {},
            style: { stroke: "#c3c0ff", strokeWidth: 2 },
          },
          eds,
        ),
      ),
    [setEdges],
  );

  const addPaletteNode = useCallback(
    (kind: NodeKind) => {
      const nid = newId();
      const defaultConfig: Record<string, unknown> =
        kind === "llm"
          ? { prompt: "" }
          : kind === "tool"
            ? { tool_name: "" }
            : kind === "subagent"
              ? { subagent_id: "" }
              : kind === "asr"
                ? { provider: "openai_whisper", language: "" }
                : kind === "tts"
                  ? { provider: "openai_tts", voice: "nova" }
                  : {};
      setNodes((prev) => [
        ...prev,
        {
          id: nid,
          type: "af_node",
          position: { x: 120 + prev.length * 30, y: 120 + prev.length * 20 },
          data: { nodeType: kind, config: defaultConfig },
        },
      ]);
      if (!entryPoint) setEntryPoint(nid);
    },
    [entryPoint, setNodes],
  );

  const applyQuickStart = useCallback(
    (tpl: GraphQuickstart) => {
      setNodes(
        tpl.nodes.map((n, i) => ({
          id: n.id,
          type: "af_node",
          position: {
            x: 80 + (i % 3) * 320,
            y: 80 + Math.floor(i / 3) * 200,
          },
          data: { nodeType: n.type, config: n.config },
        })),
      );
      setEdges(
        tpl.edges.map((e, i) => ({
          id: `e_${i}_${e.from}_${e.to}`,
          source: e.from,
          target: e.to,
          data: e.condition ? { condition: e.condition } : {},
          label: e.condition,
          style: { stroke: "#c3c0ff", strokeWidth: 2 },
        })),
      );
      setEntryPoint(tpl.entry);
      setSaveMsg(null);
      setSelectedEdgeId(null);
      setShowTemplateOverlay(false);
    },
    [setNodes, setEdges],
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
      return { id: n.id, type: nt, config: n.data.config ?? {} };
    });
    const ge = edges.map((e) => ({
      from: e.source,
      to: e.target,
      condition:
        e.data && typeof e.data === "object" && "condition" in e.data
          ? ((e.data as { condition?: string | null }).condition ?? null)
          : null,
    }));
    const ep =
      entryPoint && nodeIds.includes(entryPoint)
        ? entryPoint
        : (nodeIds[0] ?? "");
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
          model_config: modelConfig,
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

  if (error && !agent) return <p className="px-4 text-af-error">{error}</p>;
  if (!agent) return <p className="px-4 text-af-muted">Loading…</p>;

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 pb-12 md:px-8">
      <div className="flex flex-wrap items-center gap-4">
        <Link
          href={`/agents/${id}`}
          className="text-sm text-af-muted hover:text-af-primary"
        >
          ← {agent.name}
        </Link>
      </div>
      <span className="af-kicker block text-af-primary">[ BUILDER ]</span>
      <h1 className="font-sans text-2xl font-bold text-white md:text-3xl">
        Visual <span className="af-serif-italic text-af-primary">graph</span>
      </h1>
      <p className="max-w-2xl text-sm text-af-muted">
        Add nodes, connect edges, optional{" "}
        <strong className="text-af-on-surface">condition</strong> strings
        (substring match on last AI message). Set entry point, save.
      </p>

      <div className="flex flex-wrap gap-2">
        {(
          [
            ["llm", "LLM"],
            ["tool", "Tool"],
            ["subagent", "Subagent"],
            ["conditional", "Router"],
            ["interrupt", "Interrupt (HITL)"],
            ["asr", "ASR (Mic)"],
            ["tts", "TTS (Speaker)"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            type="button"
            onClick={() => addPaletteNode(k)}
            className="rounded-lg border border-af-border px-3 py-1.5 text-xs font-bold text-af-on-surface transition-colors hover:border-af-primary hover:text-af-primary"
          >
            + {label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
          Quick start
        </span>
        {GRAPH_QUICKSTARTS.map((tpl) => (
          <button
            key={tpl.label}
            type="button"
            onClick={() => applyQuickStart(tpl)}
            className="rounded-lg border border-af-border/60 px-3 py-1 text-[10px] font-bold uppercase tracking-wide text-af-muted transition-colors hover:border-af-primary/50 hover:text-af-primary"
          >
            {tpl.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
            Entry point
          </label>
          <select
            value={entryPoint}
            onChange={(e) => setEntryPoint(e.target.value)}
            className="af-input max-w-xs py-2 text-sm"
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
          className="af-btn-primary px-6 py-2 text-sm disabled:opacity-50"
        >
          {busy ? "Saving…" : "Save graph"}
        </button>
        {saveMsg && <span className="text-sm text-af-tertiary">{saveMsg}</span>}
      </div>

      {selectedEdgeId && (
        <div className="af-card flex flex-wrap items-end gap-3 p-4">
          <div>
            <label className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Edge condition (optional)
            </label>
            <input
              value={edgeConditionDraft}
              onChange={(e) => setEdgeConditionDraft(e.target.value)}
              placeholder="e.g. approved — substring on last AI output"
              className="af-input w-72 max-w-full text-sm"
            />
          </div>
          <button
            type="button"
            onClick={applyEdgeCondition}
            className="rounded-lg border border-af-border px-4 py-2 text-sm text-af-on-surface hover:bg-white/5"
          >
            Apply
          </button>
          <button
            type="button"
            onClick={() => setSelectedEdgeId(null)}
            className="text-sm text-af-muted hover:text-white"
          >
            Clear selection
          </button>
        </div>
      )}

      {/* Model Configuration */}
      <div className="af-card p-4 space-y-3">
        <div className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim border-b border-white/10 pb-2">
          Model Configuration
        </div>
        <div className="flex flex-wrap gap-4 items-end">
          {/* Provider */}
          <div className="space-y-1">
            <label className="text-[10px] uppercase text-af-muted-dim">Provider</label>
            <select
              value={modelConfig.provider}
              onChange={(e) => {
                const provider = e.target.value;
                const defaults: Record<string, string> = {
                  openai: "gpt-5.4-mini",
                  google: "gemini-3-flash",
                  gemini: "gemini-3-flash",
                  anthropic: "claude-sonnet-4-5",
                  mock: "mock",
                };
                setModelConfig(prev => ({
                  ...prev,
                  provider,
                  model: defaults[provider] || prev.model,
                }));
              }}
              className="af-input py-1.5 text-xs"
            >
              <option value="openai">OpenAI</option>
              <option value="google">Google Gemini</option>
              <option value="anthropic">Anthropic</option>
              <option value="mock">Mock (testing)</option>
            </select>
          </div>

          {/* Model */}
          <div className="space-y-1">
            <label className="text-[10px] uppercase text-af-muted-dim">Model</label>
            <input
              value={modelConfig.model}
              onChange={(e) => setModelConfig(prev => ({ ...prev, model: e.target.value }))}
              placeholder="e.g. gpt-5.4-mini"
              className="af-input py-1.5 text-xs w-44"
            />
          </div>

          {/* Temperature */}
          <div className="space-y-1 min-w-[160px]">
            <label className="text-[10px] uppercase text-af-muted-dim">
              Temperature: {modelConfig.temperature.toFixed(1)}
            </label>
            <input
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={modelConfig.temperature}
              onChange={(e) => setModelConfig(prev => ({ ...prev, temperature: parseFloat(e.target.value) }))}
              className="w-full accent-af-primary"
            />
            <div className="flex justify-between text-[9px] text-af-muted">
              <span>Précis (0)</span>
              <span>Créatif (2)</span>
            </div>
          </div>
        </div>
      </div>

      {error && <p className="text-sm text-af-error">{error}</p>}

      <div className="relative h-[600px] w-full overflow-hidden rounded-xl border border-af-border bg-af-surface-void [&_.react-flow]:bg-af-surface-void">
        <DeployedSpeechContext.Provider value={deployedSpeech}>
          <ReactFlow
            colorMode="dark"
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onEdgeClick={(_, edge) => setSelectedEdgeId(edge.id)}
            nodeTypes={nodeTypes}
            fitView
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </DeployedSpeechContext.Provider>

        {showTemplateOverlay && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-6 bg-af-surface-void/90 backdrop-blur-sm">
            <div className="text-center">
              <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                Démarrage rapide
              </p>
              <h2 className="mt-1 text-lg font-bold text-white">
                Choisissez un template
              </h2>
              <p className="mt-1 text-xs text-af-muted">
                ou partez d&apos;un canvas vide
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-4 px-4">
              {GRAPH_QUICKSTARTS.map((tpl) => (
                <button
                  key={tpl.label}
                  type="button"
                  onClick={() => applyQuickStart(tpl)}
                  className="af-card flex w-48 flex-col items-start gap-2 p-4 text-left transition-colors hover:border-af-primary/60 hover:bg-af-surface-container/60"
                >
                  <span className="text-2xl">{tpl.icon}</span>
                  <span className="font-bold text-white">{tpl.label}</span>
                  <span className="text-[11px] text-af-muted">{tpl.description}</span>
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setShowTemplateOverlay(false)}
              className="rounded-lg border border-af-border/40 px-5 py-2 text-sm text-af-muted transition-colors hover:border-af-border hover:text-af-on-surface"
            >
              Canvas vide
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AgentBuilderPage() {
  return (
    <ReactFlowProvider>
      <BuilderInner />
    </ReactFlowProvider>
  );
}
