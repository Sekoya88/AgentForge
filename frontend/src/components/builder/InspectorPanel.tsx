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
  llm:          { color: "var(--af-node-llm)",         icon: "psychology",   label: "LLM" },
  tool:         { color: "var(--af-node-tool)",        icon: "build",        label: "Tool" },
  conditional:  { color: "var(--af-node-conditional)", icon: "call_split",   label: "Conditional" },
  interrupt:    { color: "var(--af-node-interrupt)",   icon: "pause_circle", label: "Interrupt" },
  subagent:     { color: "var(--af-node-subagent)",    icon: "account_tree", label: "Subagent" },
  asr:          { color: "var(--af-node-speech)",      icon: "mic",          label: "ASR" },
  tts:          { color: "var(--af-node-speech)",      icon: "volume_up",    label: "TTS" },
  memory_save:  { color: "var(--af-node-memory)",      icon: "save",         label: "Memory Save" },
  memory_recall:{ color: "var(--af-node-memory)",      icon: "memory",       label: "Memory Recall" },
};

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
        {label}
      </label>
      {children}
    </div>
  );
}

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
            data: {
              ...n.data,
              config: { ...(n.data.config as NodeConfig), [key]: value },
            },
          };
        }),
      );
    },
    [nodeId, setNodes],
  );

  if (!nodeId || !nodeType) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <span className="material-symbols-outlined text-3xl text-af-muted-dim">touch_app</span>
        <p className="text-xs text-af-muted">Click a node to inspect and configure it.</p>
      </div>
    );
  }

  const meta = NODE_META[nodeType] ?? { color: "#6b7280", icon: "widgets", label: nodeType };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between border-b border-af-border/60 px-4 py-3"
        style={{ borderLeftColor: meta.color, borderLeftWidth: "3px" }}
      >
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-base" style={{ color: meta.color }}>
            {meta.icon}
          </span>
          <div>
            <div
              className="text-[10px] font-bold uppercase tracking-widest"
              style={{ color: meta.color }}
            >
              {meta.label}
            </div>
            <div className="af-mono text-[10px] text-af-muted-dim">{nodeId}</div>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="flex h-6 w-6 items-center justify-center rounded text-af-muted-dim transition-colors hover:text-af-on-surface"
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
    return (
      <div className="space-y-4">
        <Field label="System Prompt">
          <textarea
            value={str("prompt")}
            onChange={(e) => updateConfig("prompt", e.target.value)}
            placeholder="You are a helpful assistant..."
            rows={6}
            className="af-input w-full resize-y p-2 text-xs"
          />
        </Field>
        <Field label="Provider override (optional)">
          <select
            value={str("provider")}
            onChange={(e) => updateConfig("provider", e.target.value)}
            className="af-input w-full p-2 text-xs"
          >
            <option value="">— inherit from agent —</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="google">Google</option>
            <option value="ollama">Ollama</option>
            <option value="mistral">Mistral</option>
          </select>
        </Field>
        <Field label="Model override (optional)">
          <input
            value={str("model")}
            onChange={(e) => updateConfig("model", e.target.value)}
            placeholder="e.g. gpt-4o-mini"
            className="af-input w-full p-2 text-xs"
          />
        </Field>
        <Field label="Temperature (0–2)">
          <input
            type="number"
            min={0}
            max={2}
            step={0.1}
            value={str("temperature")}
            onChange={(e) => updateConfig("temperature", e.target.value)}
            placeholder="0.7"
            className="af-input w-full p-2 text-xs"
          />
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
            className="af-input w-full p-2 text-xs"
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
            <input
              type="number"
              min={1}
              max={20}
              value={str("top_k", "5")}
              onChange={(e) => updateConfig("top_k", e.target.value)}
              className="af-input w-full p-2 text-xs"
            />
          </Field>
        )}
        {str("tool_name") === "web_search" && (
          <Field label="Default query (optional)">
            <input
              value={str("query")}
              onChange={(e) => updateConfig("query", e.target.value)}
              placeholder="Leave empty to use last message"
              className="af-input w-full p-2 text-xs"
            />
          </Field>
        )}
      </div>
    );
  }

  if (nodeType === "subagent") {
    return (
      <div className="space-y-4">
        <Field label="Subagent ID (UUID)">
          <input
            value={str("subagent_id")}
            onChange={(e) => updateConfig("subagent_id", e.target.value)}
            placeholder="Agent UUID"
            className="af-input af-mono w-full p-2 text-xs"
          />
        </Field>
        <Field label="Label">
          <input
            value={str("label")}
            onChange={(e) => updateConfig("label", e.target.value)}
            placeholder="e.g. Researcher"
            className="af-input w-full p-2 text-xs"
          />
        </Field>
      </div>
    );
  }

  if (nodeType === "conditional") {
    return (
      <div className="space-y-3">
        <p className="text-xs text-af-muted">
          Routes based on edge conditions. Configure conditions on each outgoing edge (click an edge
          to set its condition string).
        </p>
        <div className="rounded-lg border border-af-border/40 bg-af-surface-void/40 p-3 text-[10px] text-af-muted-dim">
          Supported operators: <span className="af-mono">contains</span>,{" "}
          <span className="af-mono">regex</span>, <span className="af-mono">json_path</span>,{" "}
          <span className="af-mono">always</span>
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
            className="af-input w-full p-2 text-xs"
          />
        </Field>
        <p className="text-xs text-af-muted">
          The agent pauses here and waits for a human decision before continuing.
        </p>
      </div>
    );
  }

  if (nodeType === "memory_save") {
    return (
      <div className="space-y-4">
        <Field label="Importance (0.0–1.0)">
          <input
            type="number"
            min={0}
            max={1}
            step={0.1}
            value={str("importance", "0.5")}
            onChange={(e) => updateConfig("importance", e.target.value)}
            className="af-input w-full p-2 text-xs"
          />
        </Field>
        <p className="text-xs text-af-muted">
          Saves the last human message as a memory entry for this agent. Higher importance = ranked
          higher in recall.
        </p>
      </div>
    );
  }

  if (nodeType === "memory_recall") {
    return (
      <div className="space-y-4">
        <Field label="Top K memories to inject">
          <input
            type="number"
            min={1}
            max={20}
            value={str("top_k", "5")}
            onChange={(e) => updateConfig("top_k", e.target.value)}
            className="af-input w-full p-2 text-xs"
          />
        </Field>
        <p className="text-xs text-af-muted">
          Retrieves the most semantically relevant memories for the current query and injects them
          as context before the next LLM node.
        </p>
      </div>
    );
  }

  return (
    <p className="text-xs text-af-muted">No configurable properties for this node type.</p>
  );
}
