"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type SkillRow = { id: string; name: string };
type Template = {
  slug: string;
  name: string;
  description: string;
  icon: string;
  tags: string[];
};
type TemplateDetail = Template & {
  graph_definition: object;
  model_config: Record<string, unknown>;
};
type DeployedModel = { id: string; base_model: string; inference_endpoint: string };

const TAG_COLORS: Record<string, string> = {
  beginner: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  intermediate: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  advanced: "bg-red-500/10 text-red-400 border-red-500/20",
  llm: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20",
  rag: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  knowledge: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  skills: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  tool: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  security: "bg-rose-500/10 text-rose-400 border-rose-500/20",
  "red-team": "bg-rose-500/10 text-rose-400 border-rose-500/20",
  code: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
  hitl: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  interrupt: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  speech: "bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-500/20",
  conversation: "bg-sky-500/10 text-sky-300 border-sky-500/20",
  fun: "bg-pink-500/10 text-pink-300 border-pink-500/20",
  fetch: "bg-teal-500/10 text-teal-300 border-teal-500/20",
  chain: "bg-violet-500/10 text-violet-300 border-violet-500/20",
  tutor: "bg-lime-500/10 text-lime-300 border-lime-500/20",
};

type ProviderKey = "mock" | "openai" | "gemini" | "anthropic" | "finetuned";

const PROVIDER_CARDS: { value: ProviderKey; label: string; description: string; icon: string; color: string }[] = [
  {
    value: "mock",
    label: "Mock",
    description: "Offline echo — best for dev & testing",
    icon: "code",
    color: "border-af-border/60 hover:border-emerald-500/60",
  },
  {
    value: "openai",
    label: "OpenAI",
    description: "GPT models — requires API key",
    icon: "auto_awesome",
    color: "border-af-border/60 hover:border-sky-500/60",
  },
  {
    value: "anthropic",
    label: "Anthropic",
    description: "Claude models — requires API key",
    icon: "android",
    color: "border-af-border/60 hover:border-af-primary/60",
  },
  {
    value: "gemini",
    label: "Gemini",
    description: "Google models — requires API key",
    icon: "stars",
    color: "border-af-border/60 hover:border-amber-500/60",
  },
  {
    value: "finetuned",
    label: "Fine-tuned",
    description: "Your deployed QLoRA model",
    icon: "tune",
    color: "border-af-border/60 hover:border-fuchsia-500/60",
  },
];

const ACTIVE_COLOR: Record<ProviderKey, string> = {
  mock: "border-emerald-500/60 bg-emerald-500/5",
  openai: "border-sky-500/60 bg-sky-500/5",
  anthropic: "border-af-primary/60 bg-af-primary/5",
  gemini: "border-amber-500/60 bg-amber-500/5",
  finetuned: "border-fuchsia-500/60 bg-fuchsia-500/5",
};

type GraphNode = { id: string; type: string; config?: Record<string, unknown> };
type GraphEdge = { from: string; to: string };
type GraphDef = { nodes: GraphNode[]; edges: GraphEdge[]; entry_point: string };

const NODE_TYPES = ["llm", "tool", "decision", "code", "retrieval", "human"] as const;
const NODE_TYPE_ICONS: Record<string, string> = {
  llm: "smart_toy",
  tool: "build",
  decision: "call_split",
  code: "code",
  retrieval: "search",
  human: "person",
};

function buildDefaultGraph(systemPrompt: string): object {
  return {
    nodes: [
      { id: "n1", type: "llm", config: { prompt: systemPrompt } },
    ],
    edges: [],
    entry_point: "n1",
  };
}

function parseGraph(json: string): GraphDef | null {
  try {
    return JSON.parse(json) as GraphDef;
  } catch {
    return null;
  }
}

function deleteNodeFromGraph(json: string, nodeId: string): string {
  try {
    const g = JSON.parse(json) as GraphDef;
    g.nodes = g.nodes.filter((n) => n.id !== nodeId);
    g.edges = g.edges.filter((e) => e.from !== nodeId && e.to !== nodeId);
    if (g.entry_point === nodeId) {
      g.entry_point = g.nodes[0]?.id ?? "";
    }
    return JSON.stringify(g, null, 2);
  } catch {
    return json;
  }
}

function addNodeToGraph(json: string, type: string): string {
  try {
    const g = JSON.parse(json) as GraphDef;
    const existingIds = new Set(g.nodes.map((n) => n.id));
    let idx = g.nodes.length + 1;
    while (existingIds.has(`n${idx}`)) idx++;
    const newNode: GraphNode = { id: `n${idx}`, type, config: type === "llm" ? { prompt: "" } : {} };
    g.nodes = [...g.nodes, newNode];
    return JSON.stringify(g, null, 2);
  } catch {
    return json;
  }
}

function extractPromptFromGraph(json: string): string {
  try {
    const g = JSON.parse(json) as { nodes?: { config?: { prompt?: string } }[] };
    return g.nodes?.[0]?.config?.prompt ?? "";
  } catch {
    return "";
  }
}

function patchPromptInGraph(json: string, prompt: string): string {
  try {
    const g = JSON.parse(json) as { nodes?: { config?: { prompt?: string } }[] };
    if (g.nodes?.[0]?.config) {
      g.nodes[0].config.prompt = prompt;
    }
    return JSON.stringify(g, null, 2);
  } catch {
    return json;
  }
}

export default function NewAgentPage() {
  const router = useRouter();

  // Core state
  const [name, setName] = useState("My agent");
  const [systemPrompt, setSystemPrompt] = useState("You are a helpful assistant.");
  const [provider, setProvider] = useState<ProviderKey>("mock");
  const [graphJson, setGraphJson] = useState(
    JSON.stringify(buildDefaultGraph("You are a helpful assistant."), null, 2),
  );
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Resources
  const [registrySkills, setRegistrySkills] = useState<SkillRow[]>([]);
  const [skillPick, setSkillPick] = useState<Set<string>>(new Set());
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [deployedModels, setDeployedModels] = useState<DeployedModel[]>([]);
  const [selectedFinetune, setSelectedFinetune] = useState("");

  // AI generation
  const [genPrompt, setGenPrompt] = useState("");
  const [generating, setGenerating] = useState(false);

  // Submit
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [applyingTemplate, setApplyingTemplate] = useState(false);
  const [addingNodeType, setAddingNodeType] = useState<string | null>(null);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const [rows, tmpl, deployed] = await Promise.all([
          api<SkillRow[]>("/api/v1/skills").catch(() => [] as SkillRow[]),
          api<Template[]>("/api/v1/templates").catch(() => [] as Template[]),
          api<DeployedModel[]>("/api/v1/finetune/deployed").catch(() => [] as DeployedModel[]),
        ]);
        if (!c) {
          setRegistrySkills(rows);
          setTemplates(tmpl);
          setDeployedModels(deployed);
        }
      } catch { /* unauthenticated */ }
    })();
    return () => { c = true; };
  }, []);

  function handleSystemPromptChange(val: string) {
    setSystemPrompt(val);
    setGraphJson((prev) => patchPromptInGraph(prev, val));
  }

  function handleGraphJsonChange(val: string) {
    setGraphJson(val);
    const extracted = extractPromptFromGraph(val);
    if (extracted) setSystemPrompt(extracted);
  }

  async function applyTemplate(slug: string) {
    if (applyingTemplate) return;
    setApplyingTemplate(true);
    setSelectedSlug(slug);
    try {
      const detail = await api<TemplateDetail>(`/api/v1/templates/${slug}`);
      setName(detail.name);
      const json = JSON.stringify(detail.graph_definition, null, 2);
      setGraphJson(json);
      setSystemPrompt(extractPromptFromGraph(json));
      const p = String(detail.model_config?.provider ?? "mock");
      const found = PROVIDER_CARDS.find((pr) => pr.value === p);
      setProvider((found?.value ?? "mock") as ProviderKey);
    } catch {
      setSelectedSlug(null);
    } finally {
      setApplyingTemplate(false);
    }
  }

  function toggleSkill(sid: string) {
    setSkillPick((prev) => {
      const next = new Set(prev);
      if (next.has(sid)) { next.delete(sid); } else { next.add(sid); }
      return next;
    });
  }

  async function onGenerate() {
    if (!genPrompt.trim()) return;
    setGenerating(true);
    setError(null);
    try {
      const res = await api<{
        name: string;
        graph_definition: object;
        model_config: Record<string, unknown>;
      }>("/api/v1/generate/agent", {
        method: "POST",
        body: JSON.stringify({ prompt: genPrompt }),
      });
      setName(res.name);
      const json = JSON.stringify(res.graph_definition, null, 2);
      setGraphJson(json);
      setSystemPrompt(extractPromptFromGraph(json));
      setSelectedSlug(null);
      if (res.model_config?.provider) {
        const found = PROVIDER_CARDS.find((p) => p.value === res.model_config.provider);
        if (found) setProvider(found.value);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generate failed");
    } finally {
      setGenerating(false);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    let graph_definition: object;
    try {
      graph_definition = JSON.parse(graphJson) as object;
    } catch {
      setError("Invalid JSON in graph definition");
      return;
    }
    setLoading(true);
    try {
      let model_config: Record<string, unknown>;
      if (provider === "finetuned") {
        if (!selectedFinetune) {
          setError("Select a deployed fine-tuned model");
          setLoading(false);
          return;
        }
        const ft = deployedModels.find((d) => d.id === selectedFinetune);
        model_config = {
          provider: "finetuned",
          finetune_job_id: selectedFinetune,
          model: ft?.base_model ?? undefined,
          temperature: 0.7,
        };
      } else if (provider === "openai") {
        model_config = { provider: "openai", model: "gpt-4o", temperature: 0.2 };
      } else if (provider === "anthropic") {
        model_config = { provider: "anthropic", model: "claude-sonnet-4-6", temperature: 0.2 };
      } else if (provider === "gemini") {
        model_config = { provider: "gemini", model: "gemini-2.0-flash", temperature: 0.2 };
      } else {
        model_config = { provider: "mock", temperature: 0.2 };
      }

      const agent = await api<{ id: string }>("/api/v1/agents", {
        method: "POST",
        body: JSON.stringify({
          name,
          description: null,
          graph_definition,
          model_config,
          skills: [...skillPick],
        }),
      });
      router.push(`/agents/${agent.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 md:px-8">
      {/* Header */}
      <div className="mb-8">
        <Link href="/agents" className="mb-4 inline-flex items-center gap-1 text-xs text-af-muted transition-colors hover:text-af-primary">
          <span className="material-symbols-outlined text-sm">arrow_back</span>
          Back to Agents
        </Link>
        <span className="af-kicker mb-2 block">[ NEW AGENT ]</span>
        <h1 className="font-sans text-3xl font-bold tracking-tight text-white md:text-4xl">
          Create <span className="af-serif-italic text-af-primary">agent</span>
        </h1>
      </div>

      {/* ── Step 1: AI Generation ── */}
      <section className="mb-6">
        <div className="mb-3 flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-af-primary text-xs font-bold text-black">1</span>
          <span className="text-sm font-bold text-white">Start from a description</span>
          <span className="text-xs text-af-muted-dim">(optional)</span>
        </div>
        <div className="rounded-xl border border-af-primary/20 bg-af-primary/5 p-4">
          <div className="flex gap-2">
            <input
              value={genPrompt}
              onChange={(e) => setGenPrompt(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") void onGenerate(); }}
              placeholder="A research agent that searches the web and summarizes findings…"
              className="af-input flex-1 text-sm"
            />
            <button
              type="button"
              onClick={() => void onGenerate()}
              disabled={generating || !genPrompt.trim()}
              className="af-btn-primary flex shrink-0 items-center gap-2 px-5 py-2 text-sm disabled:opacity-50"
            >
              {generating ? (
                <span className="material-symbols-outlined animate-spin text-sm">autorenew</span>
              ) : (
                <span className="material-symbols-outlined text-sm">auto_awesome</span>
              )}
              {generating ? "Generating…" : "Generate"}
            </button>
          </div>
          <p className="mt-2 text-[11px] text-af-muted-dim">
            Describe what your agent should do. AI will configure the graph, name, and system prompt.
          </p>
        </div>
      </section>

      {/* ── Step 2: Templates ── */}
      {templates.length > 0 && (
        <section className="mb-6">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-af-surface-high text-xs font-bold text-af-muted border border-af-border/60">2</span>
              <span className="text-sm font-bold text-white">Or pick a template</span>
              <span className="text-xs text-af-muted-dim">(optional)</span>
            </div>
            {selectedSlug && (
              <button
                type="button"
                onClick={() => {
                  setSelectedSlug(null);
                  setName("My agent");
                  setSystemPrompt("You are a helpful assistant.");
                  const defaultGraph = JSON.stringify(buildDefaultGraph("You are a helpful assistant."), null, 2);
                  setGraphJson(defaultGraph);
                  setProvider("mock");
                }}
                className="text-xs text-af-muted transition-colors hover:text-white"
              >
                Clear
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {templates.map((t) => (
              <button
                key={t.slug}
                type="button"
                onClick={() => void applyTemplate(t.slug)}
                className={[
                  "group flex items-start gap-3 rounded-xl border p-4 text-left transition-all",
                  selectedSlug === t.slug
                    ? "border-af-primary bg-af-primary/10 shadow-[0_0_16px_rgba(99,102,241,0.12)]"
                    : "border-af-border/40 bg-af-surface-container/40 hover:border-af-primary/50 hover:bg-af-primary/5",
                ].join(" ")}
              >
                <span
                  className={["material-symbols-outlined mt-0.5 shrink-0 text-xl", selectedSlug === t.slug ? "text-af-primary" : "text-af-muted"].join(" ")}
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  {t.icon}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-bold text-white">{t.name}</span>
                    {selectedSlug === t.slug && (
                      <span className="material-symbols-outlined shrink-0 text-sm text-af-primary">check_circle</span>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs leading-relaxed text-af-muted">{t.description}</p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {t.tags.slice(0, 4).map((tag) => (
                      <span
                        key={tag}
                        className={["rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider", TAG_COLORS[tag] ?? "bg-white/5 text-af-muted border-white/10"].join(" ")}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </section>
      )}

      {/* ── Step 3: Configure ── */}
      <section className="mb-6">
        <div className="mb-3 flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-af-surface-high text-xs font-bold text-af-muted border border-af-border/60">3</span>
          <span className="text-sm font-bold text-white">Configure</span>
        </div>

        <form onSubmit={onSubmit} className="space-y-5">
          {/* Name */}
          <div className="rounded-xl border border-af-border/40 bg-af-surface-container/40 p-5">
            <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Agent name
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My agent"
              className="af-input w-full text-sm"
              required
            />
          </div>

          {/* System prompt */}
          <div className="rounded-xl border border-af-border/40 bg-af-surface-container/40 p-5">
            <label className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              System prompt
            </label>
            <p className="mb-3 text-[11px] text-af-muted-dim">
              Defines the agent&apos;s role, behavior, and constraints.
            </p>
            <textarea
              rows={5}
              value={systemPrompt}
              onChange={(e) => handleSystemPromptChange(e.target.value)}
              placeholder="You are a helpful assistant specialized in…"
              className="af-input w-full resize-y font-mono text-xs leading-relaxed"
            />
          </div>

          {/* Provider */}
          <div className="rounded-xl border border-af-border/40 bg-af-surface-container/40 p-5">
            <label className="mb-3 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              LLM provider
            </label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
              {PROVIDER_CARDS.map((p) => {
                const isActive = provider === p.value;
                return (
                  <button
                    key={p.value}
                    type="button"
                    onClick={() => setProvider(p.value)}
                    className={[
                      "flex flex-col items-center gap-1.5 rounded-xl border p-3 text-center transition-all",
                      isActive ? ACTIVE_COLOR[p.value] : `${p.color} bg-transparent`,
                    ].join(" ")}
                  >
                    <span
                      className={["material-symbols-outlined text-xl", isActive ? "text-af-primary" : "text-af-muted"].join(" ")}
                      style={{ fontVariationSettings: "'FILL' 1" }}
                    >
                      {p.icon}
                    </span>
                    <span className={["text-xs font-bold", isActive ? "text-white" : "text-af-muted"].join(" ")}>
                      {p.label}
                    </span>
                  </button>
                );
              })}
            </div>
            <p className="mt-2 text-[11px] text-af-muted-dim">
              {PROVIDER_CARDS.find((p) => p.value === provider)?.description}
            </p>
            {provider === "finetuned" && (
              <div className="mt-3">
                {deployedModels.length === 0 ? (
                  <p className="text-xs text-af-muted-dim">
                    No deployed models.{" "}
                    <Link href="/finetune" className="text-af-primary hover:underline">
                      Fine-tune one first
                    </Link>
                    .
                  </p>
                ) : (
                  <select
                    value={selectedFinetune}
                    onChange={(e) => setSelectedFinetune(e.target.value)}
                    className="af-input mt-1 w-full text-sm"
                  >
                    <option value="">Select a deployed model…</option>
                    {deployedModels.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.base_model} ({m.id.slice(0, 8)})
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}
          </div>

          {/* Skills */}
          {registrySkills.length > 0 && (
            <div className="rounded-xl border border-af-border/40 bg-af-surface-container/40 p-5">
              <label className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                Skills <span className="normal-case font-normal text-af-muted-dim">(optional)</span>
              </label>
              <p className="mb-3 text-[11px] text-af-muted-dim">
                Attach Python tool bundles the agent can call.
              </p>
              <div className="flex flex-wrap gap-2">
                {registrySkills.map((s) => {
                  const active = skillPick.has(s.id);
                  return (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => toggleSkill(s.id)}
                      className={[
                        "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-all",
                        active
                          ? "border-af-primary/60 bg-af-primary/10 text-af-primary"
                          : "border-af-border/60 text-af-muted hover:border-af-primary/40 hover:text-af-on-surface",
                      ].join(" ")}
                    >
                      <span className="material-symbols-outlined text-xs">
                        {active ? "check_circle" : "psychology"}
                      </span>
                      {s.name}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Graph nodes */}
          {(() => {
            const g = parseGraph(graphJson);
            if (!g) return null;
            return (
              <div className="rounded-xl border border-af-border/40 bg-af-surface-container/40 p-5">
                <div className="mb-3 flex items-center justify-between">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                    Graph nodes
                  </label>
                  <span className="text-[10px] text-af-muted-dim">{g.nodes.length} node{g.nodes.length !== 1 ? "s" : ""}</span>
                </div>
                <div className="space-y-2">
                  {g.nodes.map((node) => (
                    <div
                      key={node.id}
                      className="flex items-center gap-3 rounded-lg border border-af-border/30 bg-af-surface-high/40 px-3 py-2.5"
                    >
                      <span
                        className="material-symbols-outlined shrink-0 text-base text-af-muted-dim"
                        style={{ fontVariationSettings: "'FILL' 1" }}
                      >
                        {NODE_TYPE_ICONS[node.type] ?? "circle"}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-white">{node.id}</span>
                          {node.id === g.entry_point && (
                            <span className="rounded border border-af-primary/40 bg-af-primary/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-af-primary">
                              entry
                            </span>
                          )}
                        </div>
                        <span className="text-[11px] text-af-muted">{node.type}</span>
                      </div>
                      <button
                        type="button"
                        disabled={g.nodes.length <= 1}
                        title={g.nodes.length <= 1 ? "Cannot delete the only node" : `Delete node ${node.id}`}
                        onClick={() => {
                          const updated = deleteNodeFromGraph(graphJson, node.id);
                          setGraphJson(updated);
                          const extracted = extractPromptFromGraph(updated);
                          if (extracted) setSystemPrompt(extracted);
                        }}
                        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-af-muted transition-colors hover:bg-red-500/10 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-30"
                      >
                        <span className="material-symbols-outlined text-sm">delete</span>
                      </button>
                    </div>
                  ))}
                </div>

                {/* Add node */}
                <div className="mt-3 flex items-center gap-2">
                  {addingNodeType === null ? (
                    <button
                      type="button"
                      onClick={() => setAddingNodeType("llm")}
                      className="flex items-center gap-1.5 rounded-lg border border-dashed border-af-border/60 px-3 py-2 text-xs text-af-muted transition-colors hover:border-af-primary/50 hover:text-af-primary"
                    >
                      <span className="material-symbols-outlined text-sm">add</span>
                      Add node
                    </button>
                  ) : (
                    <>
                      <select
                        value={addingNodeType}
                        onChange={(e) => setAddingNodeType(e.target.value)}
                        className="af-input flex-1 text-xs"
                      >
                        {NODE_TYPES.map((t) => (
                          <option key={t} value={t}>{t}</option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() => {
                          setGraphJson((prev) => addNodeToGraph(prev, addingNodeType));
                          setAddingNodeType(null);
                        }}
                        className="af-btn-primary px-3 py-1.5 text-xs"
                      >
                        Add
                      </button>
                      <button
                        type="button"
                        onClick={() => setAddingNodeType(null)}
                        className="px-2 py-1.5 text-xs text-af-muted hover:text-white"
                      >
                        Cancel
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })()}

          {/* Advanced: graph JSON */}
          <div className="rounded-xl border border-af-border/40 bg-af-surface-container/40">
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              className="flex w-full items-center justify-between px-5 py-4 text-left"
            >
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-sm text-af-muted-dim">schema</span>
                <span className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                  Advanced: graph definition (JSON)
                </span>
              </div>
              <span className="material-symbols-outlined text-sm text-af-muted-dim transition-transform" style={{ transform: showAdvanced ? "rotate(180deg)" : "none" }}>
                expand_more
              </span>
            </button>
            {showAdvanced && (
              <div className="border-t border-af-border/40 p-5">
                <p className="mb-3 text-[11px] text-af-muted-dim">
                  Low-level graph JSON. Editing this overrides the system prompt field above.
                  Use the <Link href="/agents" className="text-af-primary hover:underline">visual builder</Link> after creation for complex graphs.
                </p>
                <textarea
                  rows={14}
                  value={graphJson}
                  onChange={(e) => handleGraphJsonChange(e.target.value)}
                  className="af-input w-full resize-y font-mono text-xs leading-relaxed"
                />
              </div>
            )}
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-af-error/30 bg-af-error/10 px-4 py-3 text-sm text-af-error">
              <span className="material-symbols-outlined text-sm">error</span>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="af-btn-primary flex w-full items-center justify-center gap-2 py-3 text-sm font-bold disabled:opacity-50"
          >
            {loading ? (
              <>
                <span className="material-symbols-outlined animate-spin text-base">autorenew</span>
                Creating…
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-base">add_circle</span>
                Create agent
              </>
            )}
          </button>
        </form>
      </section>
    </div>
  );
}
