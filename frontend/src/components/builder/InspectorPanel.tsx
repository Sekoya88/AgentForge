"use client";

import { useCallback } from "react";
import { useReactFlow } from "@xyflow/react";

type NodeConfig = Record<string, unknown>;

interface InspectorPanelProps {
  nodeId: string | null;
  nodeType: string | null;
  config: NodeConfig;
  onClose: () => void;
}

const NODE_META: Record<string, { color: string; icon: string; label: string }> = {
  llm:           { color: "var(--af-node-llm)",         icon: "psychology",   label: "LLM" },
  tool:          { color: "var(--af-node-tool)",        icon: "build",        label: "Tool" },
  conditional:   { color: "var(--af-node-conditional)", icon: "call_split",   label: "Conditional" },
  interrupt:     { color: "var(--af-node-interrupt)",   icon: "pause_circle", label: "Interrupt" },
  subagent:      { color: "var(--af-node-subagent)",    icon: "account_tree", label: "Subagent" },
  asr:           { color: "var(--af-node-speech)",      icon: "mic",          label: "ASR" },
  tts:           { color: "var(--af-node-speech)",      icon: "volume_up",    label: "TTS" },
  memory_save:   { color: "var(--af-node-memory)",      icon: "save",         label: "Memory Save" },
  memory_recall: { color: "var(--af-node-memory)",      icon: "memory",       label: "Memory Recall" },
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
        {label}
      </label>
      {children}
    </div>
  );
}

// Enhanced input with floating label feel
const inputCls =
  "w-full rounded-lg border border-af-border/60 bg-af-surface-void/60 px-3 py-2 text-xs text-af-on-surface placeholder:text-af-muted-dim/60 backdrop-blur-sm transition-all focus:border-af-primary/60 focus:bg-af-surface-void/80 focus:ring-1 focus:ring-af-primary/20 focus:outline-none";

export function InspectorPanel({ nodeId, nodeType, config, onClose }: InspectorPanelProps) {
  const { setNodes } = useReactFlow();

  const updateConfig = useCallback(
    (key: string, value: unknown) => {
      if (!nodeId) return;
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id !== nodeId) return n;
          return {
            ...n,
            data: { ...n.data, config: { ...(n.data.config as NodeConfig), [key]: value } },
          };
        }),
      );
    },
    [nodeId, setNodes],
  );

  if (!nodeId || !nodeType) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <span
          className="material-symbols-outlined text-3xl"
          style={{ color: "var(--af-node-llm)", filter: "drop-shadow(0 0 8px var(--af-node-llm))" }}
        >
          touch_app
        </span>
        <p className="text-xs text-af-muted">Click a node to inspect and configure it.</p>
      </div>
    );
  }

  const meta = NODE_META[nodeType] ?? { color: "#6b7280", icon: "widgets", label: nodeType };

  return (
    <div
      className="flex h-full flex-col overflow-hidden"
      style={{
        background: "var(--af-glass-medium)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
      }}
    >
      {/* Header — colored gradient strip by node type */}
      <div
        className="relative flex items-center justify-between px-4 py-3 border-b"
        style={{
          borderBottomColor: `${meta.color}30`,
          background: `linear-gradient(135deg, ${meta.color}18 0%, transparent 60%)`,
        }}
      >
        {/* Left accent bar */}
        <div
          className="absolute left-0 top-0 bottom-0 w-[3px] rounded-r-full"
          style={{ background: meta.color, boxShadow: `0 0 12px ${meta.color}` }}
        />
        <div className="flex items-center gap-2 pl-2">
          <span
            className="material-symbols-outlined text-base"
            style={{ color: meta.color, filter: `drop-shadow(0 0 6px ${meta.color}80)` }}
          >
            {meta.icon}
          </span>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-widest" style={{ color: meta.color }}>
              {meta.label}
            </div>
            <div className="af-mono text-[10px] text-af-muted-dim">{nodeId}</div>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="flex h-6 w-6 items-center justify-center rounded text-af-muted-dim transition-all hover:text-af-on-surface hover:bg-white/5"
          aria-label="Close inspector"
        >
          <span className="material-symbols-outlined text-sm">close</span>
        </button>
      </div>

      {/* Form body */}
      <div className="flex-1 overflow-y-auto p-4">
        <NodeForm nodeType={nodeType} config={config} updateConfig={updateConfig} />
      </div>
    </div>
  );
}

function NodeForm({
  nodeType,
  config,
  updateConfig,
}: {
  nodeType: string;
  config: NodeConfig;
  updateConfig: (key: string, value: unknown) => void;
}) {
  const str = (k: string, fallback = "") => (config[k] as string) ?? fallback;

  if (nodeType === "llm") {
    const temp = parseFloat(str("temperature", "0.7"));
    const tempPct = Math.round((temp / 2) * 100);
    const tempColor = temp < 0.4 ? "#60a5fa" : temp < 1.0 ? "#a78bfa" : "#f97316";

    return (
      <div className="space-y-5">
        <Field label="System Prompt">
          <textarea
            value={str("prompt")}
            onChange={(e) => updateConfig("prompt", e.target.value)}
            placeholder="You are a helpful assistant..."
            rows={6}
            className={`${inputCls} resize-y leading-relaxed`}
          />
        </Field>
        <Field label="Provider override">
          <select
            value={str("provider")}
            onChange={(e) => updateConfig("provider", e.target.value)}
            className={inputCls}
          >
            <option value="">— inherit from agent —</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="google">Google</option>
            <option value="ollama">Ollama</option>
            <option value="mistral">Mistral</option>
          </select>
        </Field>
        <Field label="Model override">
          <input
            value={str("model")}
            onChange={(e) => updateConfig("model", e.target.value)}
            placeholder="e.g. gpt-4o-mini"
            className={inputCls}
          />
        </Field>
        <Field label={`Temperature — ${str("temperature", "0.7")}`}>
          {/* Visual gradient slider */}
          <div className="space-y-2">
            <input
              type="range"
              min={0}
              max={2}
              step={0.1}
              value={str("temperature", "0.7")}
              onChange={(e) => updateConfig("temperature", e.target.value)}
              className="w-full cursor-pointer accent-af-primary"
              style={{ accentColor: tempColor }}
            />
            <div className="flex items-center gap-2">
              <div
                className="h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${tempPct}%`, background: `linear-gradient(90deg, #60a5fa, ${tempColor})` }}
              />
              <span className="font-mono text-[10px]" style={{ color: tempColor }}>
                {temp < 0.4 ? "precise" : temp < 1.0 ? "balanced" : "creative"}
              </span>
            </div>
          </div>
        </Field>
      </div>
    );
  }

  if (nodeType === "tool") {
    return (
      <div className="space-y-4">
        <Field label="Tool Name">
          <select
            value={str("tool_name")}
            onChange={(e) => updateConfig("tool_name", e.target.value)}
            className={inputCls}
          >
            <option value="">— select tool —</option>
            <option value="web_search">web_search</option>
            <option value="python_repl">python_repl</option>
            <option value="retrieve">retrieve (RAG)</option>
            <option value="echo">echo</option>
            <option value="fetch">fetch</option>
          </select>
        </Field>
        {str("tool_name") === "retrieve" && (
          <Field label="Top K results">
            <input type="number" min={1} max={20} value={str("top_k", "5")}
              onChange={(e) => updateConfig("top_k", e.target.value)} className={inputCls} />
          </Field>
        )}
        {str("tool_name") === "web_search" && (
          <Field label="Default query (optional)">
            <input value={str("query")} onChange={(e) => updateConfig("query", e.target.value)}
              placeholder="Leave empty to use last message" className={inputCls} />
          </Field>
        )}
      </div>
    );
  }

  if (nodeType === "subagent") {
    return (
      <div className="space-y-4">
        <Field label="Subagent ID (UUID)">
          <input value={str("subagent_id")} onChange={(e) => updateConfig("subagent_id", e.target.value)}
            placeholder="Agent UUID" className={`${inputCls} font-mono`} />
        </Field>
        <Field label="Label">
          <input value={str("label")} onChange={(e) => updateConfig("label", e.target.value)}
            placeholder="e.g. Researcher" className={inputCls} />
        </Field>
      </div>
    );
  }

  if (nodeType === "conditional") {
    return (
      <div className="space-y-3">
        <p className="text-xs text-af-muted leading-relaxed">
          Routes based on edge conditions. Configure conditions on each outgoing edge.
        </p>
        <div className="rounded-lg border border-af-border/40 bg-af-surface-void/40 p-3 text-[10px] text-af-muted-dim space-y-1">
          <div className="font-bold text-af-muted mb-2">Supported operators</div>
          {["contains", "regex", "json_path", "always"].map((op) => (
            <div key={op} className="flex items-center gap-2">
              <span className="w-1 h-1 rounded-full bg-af-node-conditional inline-block" />
              <code className="text-af-primary/80">{op}</code>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (nodeType === "interrupt") {
    return (
      <div className="space-y-4">
        <Field label="Allowed decisions (comma-separated)">
          <input
            value={str("allowed_decisions", "approve,reject")}
            onChange={(e) => updateConfig("allowed_decisions", e.target.value.split(",").map((s) => s.trim()))}
            placeholder="approve,reject"
            className={inputCls}
          />
        </Field>
        <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-[10px] text-af-muted leading-relaxed">
          <span className="material-symbols-outlined text-sm text-red-400 align-middle mr-1">warning</span>
          The agent pauses here and waits for a human decision before continuing.
        </div>
      </div>
    );
  }

  if (nodeType === "memory_save") {
    return (
      <div className="space-y-4">
        <Field label="Importance (0.0–1.0)">
          <input type="number" min={0} max={1} step={0.1} value={str("importance", "0.5")}
            onChange={(e) => updateConfig("importance", e.target.value)} className={inputCls} />
        </Field>
        <p className="text-xs text-af-muted leading-relaxed">
          Saves the last human message as a memory entry. Higher importance = ranked higher in recall.
        </p>
      </div>
    );
  }

  if (nodeType === "memory_recall") {
    return (
      <div className="space-y-4">
        <Field label="Top K memories to inject">
          <input type="number" min={1} max={20} value={str("top_k", "5")}
            onChange={(e) => updateConfig("top_k", e.target.value)} className={inputCls} />
        </Field>
        <p className="text-xs text-af-muted leading-relaxed">
          Retrieves the most semantically relevant memories and injects them as context before the next LLM node.
        </p>
      </div>
    );
  }

  return <p className="text-xs text-af-muted">No configurable properties for this node type.</p>;
}
