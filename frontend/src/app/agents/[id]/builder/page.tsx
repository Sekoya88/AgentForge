"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
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
import dagre from "@dagrejs/dagre";
import { ApiError, api } from "@/lib/api";
import { consumeExecutionSse } from "@/lib/sse";
import { InspectorPanel } from "@/components/builder/InspectorPanel";

type NodeKind =
  | "llm"
  | "tool"
  | "subagent"
  | "conditional"
  | "interrupt"
  | "asr"
  | "tts"
  | "memory_save"
  | "memory_recall";

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

const NODE_META: Record<string, { color: string; icon: string; label: string }> = {
  llm:         { color: "var(--af-node-llm)",         icon: "psychology",      label: "LLM" },
  tool:        { color: "var(--af-node-tool)",        icon: "build",           label: "Tool" },
  conditional: { color: "var(--af-node-conditional)", icon: "call_split",      label: "Conditional" },
  interrupt:   { color: "var(--af-node-interrupt)",   icon: "pause_circle",    label: "Interrupt" },
  subagent:    { color: "var(--af-node-subagent)",    icon: "account_tree",    label: "Subagent" },
  asr:         { color: "var(--af-node-speech)",      icon: "mic",             label: "ASR" },
  tts:         { color: "var(--af-node-speech)",      icon: "volume_up",       label: "TTS" },
  memory_save: { color: "var(--af-node-memory)",      icon: "save",            label: "Memory Save" },
  memory_recall:{ color: "var(--af-node-memory)",     icon: "memory",          label: "Memory Recall" },
};

function CustomNode({ id, data, isConnectable, selected }: NodeProps) {
  const { setNodes } = useReactFlow();
  const deployedSpeech = useContext(DeployedSpeechContext);
  const { nodeType, config } = data as { nodeType: string; config: Record<string, unknown> };
  const execState = (data as { execState?: "running" | "completed" | "failed" }).execState;
  const meta = NODE_META[nodeType] ?? { color: "#6b7280", icon: "widgets", label: nodeType };

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
    <div
      className="min-w-[240px] overflow-hidden rounded-xl backdrop-blur-md transition-all duration-200"
      style={{
        position: "relative",
        background: "var(--af-glass-medium)",
        border: `1px solid ${selected ? meta.color + "80" : "var(--af-glass-border)"}`,
        borderLeft: `3px solid ${meta.color}`,
        boxShadow: selected
          ? `0 0 0 1px ${meta.color}40, 0 0 24px ${meta.color}25, 0 12px 40px rgba(0,0,0,0.3)`
          : `0 4px 20px rgba(0,0,0,0.2), 0 0 1px var(--af-glass-border)`,
      }}
    >
      {/* Running: animated border glow */}
      {execState === "running" && (
        <div style={{
          position: "absolute", inset: -2,
          borderRadius: "inherit",
          border: `2px solid ${meta.color}`,
          boxShadow: `0 0 16px ${meta.color}60, inset 0 0 8px ${meta.color}20`,
          animation: "af-node-pulse 1.5s ease-in-out infinite",
          pointerEvents: "none",
          zIndex: 5,
        }} />
      )}
      {/* Completed badge */}
      {execState === "completed" && (
        <div style={{
          position: "absolute", top: -8, right: -8,
          width: 20, height: 20,
          borderRadius: "50%", background: "#34d399",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 11, color: "#fff", fontWeight: "bold",
          zIndex: 10, boxShadow: "0 0 10px rgba(52,211,153,0.6)",
        }}>✓</div>
      )}
      {/* Failed badge */}
      {execState === "failed" && (
        <div style={{
          position: "absolute", top: -8, right: -8,
          width: 20, height: 20,
          borderRadius: "50%", background: "#f87171",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 11, color: "#fff", fontWeight: "bold",
          zIndex: 10, boxShadow: "0 0 10px rgba(248,113,113,0.6)",
        }}>✕</div>
      )}
      <Handle
        type="target"
        position={Position.Left}
        isConnectable={isConnectable}
        className="!h-3 !w-3 !border-af-surface-void"
        style={{ backgroundColor: meta.color }}
      />
      <div
        className="mb-3 flex items-center justify-between p-4 pb-2"
        style={{
          borderBottom: `1px solid ${meta.color}20`,
          background: `linear-gradient(135deg, ${meta.color}12 0%, transparent 55%)`,
        }}
      >
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-base"
            style={{ color: meta.color, filter: `drop-shadow(0 0 5px ${meta.color}80)` }}
          >
            {meta.icon}
          </span>
          <span
            className="text-[10px] font-bold uppercase tracking-widest"
            style={{ color: meta.color }}
          >
            {meta.label}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="af-mono text-[10px] text-af-muted-dim">{id}</span>
          <button
            type="button"
            onClick={() => setNodes((nds) => nds.filter((n) => n.id !== id))}
            className="nodrag flex h-5 w-5 items-center justify-center rounded text-[10px] text-af-muted-dim hover:bg-red-500/15 hover:text-red-400 transition-all leading-none"
            title="Delete node"
          >
            ✕
          </button>
        </div>
      </div>
      <div className="px-4 pb-4">

      {nodeType === "llm" && (
        <div className="space-y-2">
          <label className="text-[10px] uppercase text-af-muted-dim">
            System Prompt
          </label>
          <textarea
            value={(config?.prompt as string) || ""}
            onChange={(e) => updateConfig("prompt", e.target.value)}
            placeholder={`Décris le rôle et comportement de l'agent...\n\nExemple : "Tu es un assistant spécialisé en finance. Tu réponds toujours en français, de façon concise, en citant des chiffres précis si disponibles."`}
            className="af-input nodrag min-h-[100px] resize-y p-2 text-xs"
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

      </div>

      <Handle
        type="source"
        position={Position.Right}
        isConnectable={isConnectable}
        className="!h-3 !w-3 !border-af-surface-void"
        style={{ backgroundColor: meta.color }}
      />
    </div>
  );
}

const nodeTypes = {
  af_node: CustomNode,
};

// ── Auto-layout with dagre ──────────────────────────────────────────────────
function layoutGraph(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  /* LR + left/right handles: reserve real node footprint so edges don’t cut through bodies */
  g.setGraph({ rankdir: "LR", nodesep: 72, ranksep: 160, marginx: 24, marginy: 24 });
  nodes.forEach((n) => g.setNode(n.id, { width: 300, height: 220 }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  return nodes.map((n) => {
    const pos = g.node(n.id);
    return { ...n, position: { x: pos.x - 150, y: pos.y - 110 } };
  });
}

// ── Undo/Redo history ───────────────────────────────────────────────────────
type GraphSnapshot = { nodes: Node[]; edges: Edge[] };

function useGraphHistory(
  nodes: Node[],
  edges: Edge[],
  setNodes: (nds: Node[]) => void,
  setEdges: (eds: Edge[]) => void,
) {
  const past = useRef<GraphSnapshot[]>([]);
  const future = useRef<GraphSnapshot[]>([]);

  const snapshot = useCallback(() => {
    past.current = [...past.current, { nodes: [...nodes], edges: [...edges] }];
    future.current = [];
  }, [nodes, edges]);

  const undo = useCallback(() => {
    if (past.current.length === 0) return;
    const prev = past.current[past.current.length - 1];
    past.current = past.current.slice(0, -1);
    future.current = [{ nodes: [...nodes], edges: [...edges] }, ...future.current];
    setNodes(prev.nodes);
    setEdges(prev.edges);
  }, [nodes, edges, setNodes, setEdges]);

  const redo = useCallback(() => {
    if (future.current.length === 0) return;
    const next = future.current[0];
    future.current = future.current.slice(1);
    past.current = [...past.current, { nodes: [...nodes], edges: [...edges] }];
    setNodes(next.nodes);
    setEdges(next.edges);
  }, [nodes, edges, setNodes, setEdges]);

  return { snapshot, undo, redo };
}

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
  const [isDirty, setIsDirty] = useState(false);
  const [nodeExecState, setNodeExecState] = useState<Record<string, "running" | "completed" | "failed">>({});
  const [isRunning, setIsRunning] = useState(false);
  const [showRunInput, setShowRunInput] = useState(false);
  const [testInput, setTestInput] = useState("");
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [inspectorNodeId, setInspectorNodeId] = useState<string | null>(null);
  const [edgeConditionDraft, setEdgeConditionDraft] = useState("");
  const [ghostEdges, setGhostEdges] = useState<
    { source: string; target: string; label?: string }[]
  >([]);
  const ghostTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const loadedRef = useRef(false);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [showTemplateOverlay, setShowTemplateOverlay] = useState(false);
  const [modelConfigOpen, setModelConfigOpen] = useState(false);
  const { fitView } = useReactFlow();

  const nodeIds = useMemo(() => nodes.map((n) => n.id), [nodes]);

  const nodesWithExec = useMemo(() =>
    nodes.map(n => ({
      ...n,
      data: { ...n.data, execState: nodeExecState[n.id] },
    })),
    [nodes, nodeExecState]
  );

  const edgesWithGhost = useMemo<Edge[]>(() => {
    const ghostAsEdges: Edge[] = ghostEdges.map((g, i) => ({
      id: `ghost_${g.source}_${g.target}_${i}`,
      type: "smoothstep",
      source: g.source,
      target: g.target,
      label: g.label,
      animated: true,
      data: { ghost: true, source: g.source, target: g.target, label: g.label },
      style: {
        stroke: "rgba(195, 192, 255, 0.5)",
        strokeWidth: 2,
        strokeDasharray: "6 4",
      },
    }));
    return [...edges, ...ghostAsEdges];
  }, [edges, ghostEdges]);

  const handleSseLine = useCallback((event: string, data: string) => {
    try {
      if (event === "node_started") {
        const parsed = JSON.parse(data) as { node_id: string };
        setNodeExecState(prev => ({ ...prev, [parsed.node_id]: "running" }));
      } else if (event === "node_completed") {
        const parsed = JSON.parse(data) as { node_id: string };
        setNodeExecState(prev => ({ ...prev, [parsed.node_id]: "completed" }));
      } else if (event === "node_failed") {
        const parsed = JSON.parse(data) as { node_id: string };
        setNodeExecState(prev => ({ ...prev, [parsed.node_id]: "failed" }));
      } else if (event === "complete" || event === "error") {
        setIsRunning(false);
      }
    } catch {
      // ignore parse errors
    }
  }, []);

  async function runTest() {
    if (!testInput.trim()) return;
    setIsRunning(true);
    setNodeExecState({});
    setShowRunInput(false);
    try {
      const exec = await api<{ execution_id: string }>(`/api/v1/agents/${id}/execute`, {
        method: "POST",
        body: JSON.stringify({ messages: [{ role: "user", content: testInput }], stream: false }),
      });
      await consumeExecutionSse(id, exec.execution_id, handleSseLine);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Execution failed");
    } finally {
      setIsRunning(false);
    }
  }

  // Graph history (undo/redo)
  const { snapshot, undo, redo } = useGraphHistory(nodes, edges, setNodes, setEdges);

  // Track dirty state after initial load
  useEffect(() => {
    if (!loadedRef.current) return;
    setIsDirty(true);
  }, [nodes, edges]);

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
              type: "smoothstep",
              source: e.from,
              target: e.to,
              data: { condition: e.condition ?? undefined },
              label: e.condition ? String(e.condition) : undefined,
              style: { stroke: "#c3c0ff", strokeWidth: 2 },
            })),
          );
          // Mark as loaded so subsequent changes trigger dirty
          setTimeout(() => { loadedRef.current = true; }, 0);
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
    (p: Connection) => {
      snapshot();
      setEdges((eds) =>
        addEdge(
          {
            ...p,
            type: "smoothstep",
            id: `e_${p.source}_${p.target}_${eds.length}`,
            data: {},
            style: { stroke: "#c3c0ff", strokeWidth: 2 },
          },
          eds,
        ),
      );
    },
    [setEdges, snapshot],
  );

  const addPaletteNode = useCallback(
    (kind: NodeKind) => {
      snapshot();
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
      setNodes((prev) => {
        const updated = [
          ...prev,
          {
            id: nid,
            type: "af_node",
            position: { x: 120 + prev.length * 30, y: 120 + prev.length * 20 },
            data: { nodeType: kind, config: defaultConfig },
          },
        ];

        // Fire suggestion request (non-blocking)
        const nodeList = updated.map((n) => ({
          id: n.id,
          type: (n.data as { nodeType?: string }).nodeType ?? "llm",
        }));
        (async () => {
          try {
            // Clear any existing ghost edges and timer
            if (ghostTimerRef.current) clearTimeout(ghostTimerRef.current);
            setGhostEdges([]);

            const data = await api<{
              suggestions: { source: string; target: string; label?: string }[];
            }>(`/api/v1/agents/${id}/suggest-connections`, {
              method: "POST",
              body: JSON.stringify({ nodes: nodeList, new_node_id: nid }),
            });

            if (data.suggestions.length > 0) {
              setGhostEdges(data.suggestions.slice(0, 3));
              ghostTimerRef.current = setTimeout(() => {
                setGhostEdges([]);
              }, 8000);
            }
          } catch {
            // non-critical — silently ignore
          }
        })();

        return updated;
      });
      if (!entryPoint) setEntryPoint(nid);
    },
    [entryPoint, id, setNodes, snapshot],
  );

  const applyQuickStart = useCallback(
    (tpl: GraphQuickstart) => {
      snapshot();
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
          type: "smoothstep",
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
    [setNodes, setEdges, snapshot],
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
      setIsDirty(false);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  function autoLayout() {
    setNodes((nds) => layoutGraph(nds, edges));
    setTimeout(() => fitView({ padding: 0.2 }), 50);
  }

  // Keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const meta = e.metaKey || e.ctrlKey;

      // Ctrl+Z / Cmd+Z — undo
      if (meta && !e.shiftKey && e.key === "z") {
        e.preventDefault();
        e.stopPropagation();
        undo();
        return;
      }
      // Ctrl+Y / Cmd+Shift+Z — redo
      if ((meta && e.key === "y") || (meta && e.shiftKey && e.key === "z")) {
        e.preventDefault();
        e.stopPropagation();
        redo();
        return;
      }
      // Ctrl+S / Cmd+S — save
      if (meta && e.key === "s") {
        e.preventDefault();
        e.stopPropagation();
        saveGraph();
        return;
      }
      // Ctrl+Shift+L — auto-layout
      if (meta && e.shiftKey && e.key === "l") {
        e.preventDefault();
        e.stopPropagation();
        autoLayout();
        return;
      }
      // Ctrl+D / Cmd+D — duplicate selected node
      if (meta && e.key === "d") {
        e.preventDefault();
        e.stopPropagation();
        if (!inspectorNodeId) return;
        const original = nodes.find((n) => n.id === inspectorNodeId);
        if (!original) return;
        snapshot();
        const nid = newId();
        setNodes((prev) => [
          ...prev,
          {
            ...original,
            id: nid,
            position: {
              x: original.position.x + 30,
              y: original.position.y + 30,
            },
            selected: false,
          },
        ]);
        return;
      }
      // Delete / Backspace — delete selected node
      if (e.key === "Delete" || e.key === "Backspace") {
        const tag = (document.activeElement as HTMLElement)?.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
        if (!inspectorNodeId) return;
        e.preventDefault();
        e.stopPropagation();
        snapshot();
        setNodes((nds) => nds.filter((n) => n.id !== inspectorNodeId));
        setEdges((eds) =>
          eds.filter(
            (ed) => ed.source !== inspectorNodeId && ed.target !== inspectorNodeId,
          ),
        );
        setInspectorNodeId(null);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [undo, redo, inspectorNodeId, nodes, edges, snapshot]);

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
            ["memory_save", "Memory Save"],
            ["memory_recall", "Memory Recall"],
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
          title="Save (Ctrl+S)"
        >
          {busy ? "Saving…" : "Save graph"}
        </button>
        <button
          type="button"
          disabled={nodeIds.length === 0}
          onClick={autoLayout}
          className="rounded-lg border border-af-border px-4 py-2 text-sm text-af-on-surface transition-colors hover:border-af-primary/60 hover:text-af-primary disabled:opacity-50"
          title="Auto-arrange (Ctrl+Shift+L)"
        >
          Arrange
        </button>
        <button
          type="button"
          disabled={isRunning || nodeIds.length === 0}
          onClick={() => setShowRunInput(v => !v)}
          className={`rounded-lg border px-4 py-2 text-sm font-bold transition-colors ${
            isRunning
              ? "cursor-wait border-violet-400/70 bg-violet-950/50 text-violet-100"
              : "border-violet-500/60 text-violet-300 hover:border-violet-400 hover:bg-violet-500/10 disabled:opacity-50"
          }`}
          title="Test run agent"
        >
          {isRunning ? "Running…" : "▶ Run"}
        </button>
        {saveMsg && <span className="text-sm text-af-tertiary">{saveMsg}</span>}
        {isDirty && !busy && (
          <span className="text-xs font-medium text-amber-400">• Unsaved changes</span>
        )}
      </div>

      {showRunInput && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-violet-500/40 bg-violet-500/10 px-4 py-3">
          <span className="text-[10px] font-bold uppercase tracking-widest text-violet-400">Test input</span>
          <input
            autoFocus
            value={testInput}
            onChange={(e) => setTestInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") runTest(); if (e.key === "Escape") setShowRunInput(false); }}
            placeholder="Type a test message and press Enter…"
            className="af-input flex-1 py-1.5 text-sm min-w-[260px]"
          />
          <button
            type="button"
            onClick={runTest}
            disabled={!testInput.trim()}
            className="rounded-lg bg-violet-600 px-4 py-1.5 text-sm font-bold text-white transition-colors hover:bg-violet-500 disabled:opacity-50"
          >
            Execute
          </button>
          <button
            type="button"
            onClick={() => setShowRunInput(false)}
            className="text-sm text-af-muted hover:text-white"
          >
            Cancel
          </button>
        </div>
      )}

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

      {/* Model configuration — collapsed by default so the canvas gets vertical space */}
      <div className="af-card overflow-hidden">
        <button
          type="button"
          onClick={() => setModelConfigOpen((o) => !o)}
          className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.03]"
        >
          <span className="material-symbols-outlined shrink-0 text-af-muted text-lg">
            {modelConfigOpen ? "expand_less" : "expand_more"}
          </span>
          <div className="min-w-0 flex-1">
            <div className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Model configuration
            </div>
            <p className="truncate text-xs text-af-muted">
              {modelConfig.provider} · {modelConfig.model} · temp{" "}
              {modelConfig.temperature.toFixed(1)}
            </p>
          </div>
        </button>
        {modelConfigOpen && (
          <div className="flex flex-wrap gap-4 border-t border-white/10 px-4 pb-4 pt-3 items-end">
            <div className="space-y-1">
              <label className="text-[10px] uppercase text-af-muted-dim">Provider</label>
              <select
                value={modelConfig.provider}
                onChange={(e) => {
                  const provider = e.target.value;
                  const defaults: Record<string, string> = {
                    openai: "gpt-5.4-mini",
                    google: "gemini-2.5-flash",
                    gemini: "gemini-2.5-flash",
                    anthropic: "claude-sonnet-4-5",
                    mock: "mock",
                  };
                  setModelConfig((prev) => ({
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

            <div className="space-y-1">
              <label className="text-[10px] uppercase text-af-muted-dim">Model</label>
              <input
                value={modelConfig.model}
                onChange={(e) =>
                  setModelConfig((prev) => ({ ...prev, model: e.target.value }))
                }
                placeholder="e.g. gpt-5.4-mini"
                className="af-input py-1.5 text-xs w-44 min-w-[11rem]"
              />
            </div>

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
                onChange={(e) =>
                  setModelConfig((prev) => ({
                    ...prev,
                    temperature: parseFloat(e.target.value),
                  }))
                }
                className="w-full accent-af-primary"
              />
              <div className="flex justify-between text-[9px] text-af-muted">
                <span>Précis (0)</span>
                <span>Créatif (2)</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {error && <p className="text-sm text-af-error">{error}</p>}

      {ghostEdges.length > 0 && (
        <div className="flex items-center gap-3 rounded-lg border border-violet-500/50 bg-violet-500/10 px-4 py-2 text-sm">
          <span className="text-[10px] font-bold uppercase tracking-widest text-violet-400">
            AI
          </span>
          <span className="text-violet-200">
            {ghostEdges.length} suggested connection{ghostEdges.length > 1 ? "s" : ""} — click a dashed edge to accept
          </span>
          <button
            type="button"
            onClick={() => {
              if (ghostTimerRef.current) clearTimeout(ghostTimerRef.current);
              setGhostEdges([]);
            }}
            className="ml-auto text-xs text-af-muted hover:text-white"
          >
            dismiss
          </button>
        </div>
      )}

      <div className="flex gap-4">
      <div className="relative min-h-[440px] h-[min(72vh,780px)] flex-1 overflow-hidden rounded-xl border border-af-border/50" style={{ background: "var(--af-glass-subtle)", boxShadow: "inset 0 0 60px rgba(0,0,0,0.15)" }}>
        <DeployedSpeechContext.Provider value={deployedSpeech}>
          <ReactFlow
            colorMode="dark"
            proOptions={{ hideAttribution: true }}
            style={{ background: "transparent" }}
            defaultEdgeOptions={{
              type: "smoothstep",
              style: { stroke: "#c3c0ff", strokeWidth: 2 },
            }}
            nodes={nodesWithExec}
            edges={edgesWithGhost}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onEdgeClick={(_, edge) => {
              if (edge.data && (edge.data as { ghost?: boolean }).ghost) {
                // Confirm ghost edge → real edge
                const gData = edge.data as {
                  ghost: boolean;
                  source: string;
                  target: string;
                  label?: string;
                };
                setGhostEdges((prev) =>
                  prev.filter(
                    (g) => !(g.source === gData.source && g.target === gData.target),
                  ),
                );
                snapshot();
                setEdges((eds) =>
                  addEdge(
                    {
                      type: "smoothstep",
                      source: gData.source,
                      target: gData.target,
                      id: `e_${gData.source}_${gData.target}_${eds.length}`,
                      label: gData.label,
                      data: {},
                      style: { stroke: "#c3c0ff", strokeWidth: 2 },
                    },
                    eds,
                  ),
                );
              } else {
                setSelectedEdgeId(edge.id);
              }
            }}
            onNodeClick={(_, node) => setInspectorNodeId(node.id)}
            onPaneClick={() => setInspectorNodeId(null)}
            nodeTypes={nodeTypes}
            fitView
          >
            <Background color="#2a2850" gap={28} size={1.2} />
            <Controls
              style={{
                background: "var(--af-glass-heavy)",
                border: "1px solid var(--af-glass-border-hover)",
                borderRadius: "10px",
                backdropFilter: "blur(12px)",
              }}
            />
            <MiniMap
              nodeColor={(n) => {
                const t = (n.data as { nodeType?: string }).nodeType ?? "";
                return NODE_META[t]?.color ?? "#6b7280";
              }}
              style={{
                background: "var(--af-glass-heavy)",
                border: "1px solid var(--af-glass-border)",
                borderRadius: "10px",
              }}
            />
          </ReactFlow>
        </DeployedSpeechContext.Provider>

        {showTemplateOverlay && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-6 backdrop-blur-md" style={{ background: "var(--af-glass-heavy)" }}>
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

      {/* Inspector panel */}
      {inspectorNodeId && (() => {
        const n = nodes.find((nd) => nd.id === inspectorNodeId);
        if (!n) return null;
        const d = n.data as { nodeType?: string; config?: Record<string, unknown> };
        return (
          <div className="min-h-[440px] h-[min(72vh,780px)] w-72 shrink-0 overflow-hidden rounded-xl border border-af-border bg-af-surface-container/80 backdrop-blur-sm">
            <InspectorPanel
              nodeId={inspectorNodeId}
              nodeType={d.nodeType ?? null}
              config={d.config ?? {}}
              onClose={() => setInspectorNodeId(null)}
            />
          </div>
        );
      })()}
      </div>

      {isRunning && (
        <div className="flex items-center gap-2 rounded-lg border border-violet-500/30 bg-violet-500/10 px-4 py-2 text-sm text-violet-300">
          <span
            className="material-symbols-outlined text-sm"
            style={{ animation: "af-spin 2s linear infinite" }}
          >
            progress_activity
          </span>
          <span>Execution in progress…</span>
          <span className="ml-2 text-xs text-af-muted-dim">
            {Object.values(nodeExecState).filter(s => s === "completed").length} nodes completed
          </span>
        </div>
      )}
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
