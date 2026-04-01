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

const DEFAULT_GRAPH = `{
  "nodes": [
    { "id": "n1", "type": "llm", "config": { "prompt": "You are helpful." } }
  ],
  "edges": [],
  "entry_point": "n1"
}`;

type DeployedModel = { id: string; base_model: string; inference_endpoint: string };

const PROVIDERS = [
  { value: "mock", label: "Mock (offline echo) — recommended for dev" },
  { value: "openai", label: "OpenAI (needs OPENAI_API_KEY on API)" },
  { value: "gemini", label: "Gemini (needs GOOGLE_API_KEY on API)" },
  { value: "finetuned", label: "Fine-tuned model (deployed via Modal)" },
] as const;

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

export default function NewAgentPage() {
  const router = useRouter();
  const [name, setName] = useState("My agent");
  const [provider, setProvider] = useState<(typeof PROVIDERS)[number]["value"]>("mock");
  const [graphJson, setGraphJson] = useState(DEFAULT_GRAPH);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [registrySkills, setRegistrySkills] = useState<SkillRow[]>([]);
  const [skillPick, setSkillPick] = useState<Set<string>>(new Set());
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [applyingTemplate, setApplyingTemplate] = useState(false);
  const [deployedModels, setDeployedModels] = useState<DeployedModel[]>([]);
  const [selectedFinetune, setSelectedFinetune] = useState("");

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
      } catch {
        /* unauthenticated */
      }
    })();
    return () => { c = true; };
  }, []);

  async function applyTemplate(slug: string) {
    if (applyingTemplate) return;
    setApplyingTemplate(true);
    setSelectedSlug(slug);
    try {
      const detail = await api<TemplateDetail>(`/api/v1/templates/${slug}`);
      setName(detail.name);
      setGraphJson(JSON.stringify(detail.graph_definition, null, 2));
      const p = String(detail.model_config?.provider ?? "mock");
      const found = PROVIDERS.find((pr) => pr.value === p);
      setProvider((found?.value ?? "mock") as (typeof PROVIDERS)[number]["value"]);
    } catch {
      setSelectedSlug(null);
    } finally {
      setApplyingTemplate(false);
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

  async function onGenerate() {
    if (!prompt.trim()) return;
    setGenerating(true);
    setError(null);
    try {
      const res = await api<{
        name: string;
        graph_definition: object;
        model_config: Record<string, unknown>;
      }>("/api/v1/generate/agent", {
        method: "POST",
        body: JSON.stringify({ prompt }),
      });
      setName(res.name);
      setGraphJson(JSON.stringify(res.graph_definition, null, 2));
      setSelectedSlug(null);
      if (res.model_config?.provider) {
        const found = PROVIDERS.find((p) => p.value === res.model_config.provider);
        if (found) setProvider(found.value as "mock" | "openai" | "gemini");
      }
    } catch (err: unknown) {
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
      setError("Invalid JSON for graph_definition");
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
        model_config = { provider: "openai", model: "gpt-5.4-mini", temperature: 0.2 };
      } else if (provider === "gemini") {
        model_config = { provider: "gemini", model: "gemini-3-flash", temperature: 0.2 };
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
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 md:px-8">
      <Link href="/agents" className="mb-6 inline-block text-sm text-af-muted hover:text-af-primary">
        ← Agents
      </Link>
      <span className="af-kicker mb-2 block">[ NEW AGENT ]</span>
      <h1 className="mb-8 font-sans text-3xl font-bold tracking-tight text-white md:text-4xl">
        Initialize <span className="af-serif-italic text-af-primary">unit</span>
      </h1>

      {/* ── Templates ── */}
      {templates.length > 0 && (
        <section className="mb-8">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Start from a template
            </p>
            {selectedSlug && (
              <button
                type="button"
                onClick={() => { setSelectedSlug(null); setName("My agent"); setGraphJson(DEFAULT_GRAPH); setProvider("mock"); }}
                className="text-xs text-af-muted hover:text-white"
              >
                Clear selection
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {templates.map((t) => (
              <button
                key={t.slug}
                type="button"
                onClick={() => void applyTemplate(t.slug)}
                className={[
                  "group relative flex flex-col items-start gap-2 rounded-xl border p-4 text-left transition-all",
                  selectedSlug === t.slug
                    ? "border-af-primary bg-af-primary/10 shadow-[0_0_16px_rgba(99,102,241,0.15)]"
                    : "border-af-border/40 bg-af-surface-container/40 hover:border-af-primary/50 hover:bg-af-primary/5",
                ].join(" ")}
              >
                <div className="flex w-full items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={[
                        "material-symbols-outlined text-xl",
                        selectedSlug === t.slug ? "text-af-primary" : "text-af-muted",
                      ].join(" ")}
                      style={{ fontVariationSettings: "'FILL' 1" }}
                    >
                      {t.icon}
                    </span>
                    <span className="font-bold text-sm text-white">{t.name}</span>
                  </div>
                  {selectedSlug === t.slug && (
                    <span className="material-symbols-outlined text-sm text-af-primary">check_circle</span>
                  )}
                </div>
                <p className="text-xs text-af-muted leading-relaxed">{t.description}</p>
                <div className="flex flex-wrap gap-1">
                  {t.tags.map((tag) => (
                    <span
                      key={tag}
                      className={[
                        "rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                        TAG_COLORS[tag] ?? "bg-white/5 text-af-muted border-white/10",
                      ].join(" ")}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </button>
            ))}
          </div>
          <div className="mt-3 flex items-center gap-3">
            <div className="h-px flex-1 bg-af-border/30" />
            <span className="text-[10px] uppercase tracking-widest text-af-muted-dim">or customize below</span>
            <div className="h-px flex-1 bg-af-border/30" />
          </div>
        </section>
      )}

      {/* ── AI Generation ── */}
      <div className="af-card mb-8 space-y-4 p-6 border-af-primary/20 bg-af-primary/5">
        <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-primary">
          AI Generation (Natural Language)
        </label>
        <div className="flex gap-2">
          <input
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="A research agent that searches the web and summarizes findings…"
            className="af-input flex-1 font-mono text-sm"
          />
          <button
            type="button"
            onClick={onGenerate}
            disabled={generating || !prompt.trim()}
            className="af-btn-primary flex items-center gap-2 px-6 py-2 text-sm disabled:opacity-50"
          >
            {generating ? (
              <>
                <span className="material-symbols-outlined animate-spin text-sm">autorenew</span>
                Generating...
              </>
            ) : (
              "Generate"
            )}
          </button>
        </div>
      </div>

      {/* ── Manual form ── */}
      <form onSubmit={onSubmit} className="af-card space-y-6 p-8">
        <div>
          <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
            Name
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="af-input font-mono"
          />
        </div>

        {registrySkills.length > 0 && (
          <div>
            <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Attach skills (optional)
            </label>
            <ul className="max-h-40 space-y-2 overflow-y-auto rounded-lg border border-af-border/60 p-3 text-sm">
              {registrySkills.map((s) => (
                <li key={s.id} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id={`new-sk-${s.id}`}
                    checked={skillPick.has(s.id)}
                    onChange={() => toggleSkill(s.id)}
                    className="rounded border-af-border"
                  />
                  <label htmlFor={`new-sk-${s.id}`} className="cursor-pointer font-mono text-af-muted">
                    {s.name}
                  </label>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div>
          <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
            LLM provider
          </label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as (typeof PROVIDERS)[number]["value"])}
            className="af-input font-mono text-sm"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
          {provider === "finetuned" && (
            <div className="mt-3">
              {deployedModels.length === 0 ? (
                <p className="text-xs text-af-muted-dim">
                  No deployed models yet.{" "}
                  <Link href="/finetune" className="text-af-primary hover:underline">
                    Fine-tune and deploy a model first
                  </Link>
                  .
                </p>
              ) : (
                <select
                  value={selectedFinetune}
                  onChange={(e) => setSelectedFinetune(e.target.value)}
                  className="af-input mt-1 font-mono text-sm"
                >
                  <option value="">Select a deployed model...</option>
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

        <div>
          <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
            graph_definition (JSON)
          </label>
          <textarea
            rows={14}
            value={graphJson}
            onChange={(e) => setGraphJson(e.target.value)}
            className="af-input min-h-[280px] resize-y font-mono text-xs leading-relaxed"
          />
        </div>

        {error && <p className="text-sm text-af-error">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="af-btn-primary flex w-full items-center justify-center gap-2 py-3 text-sm disabled:opacity-50"
        >
          {loading ? (
            <span className="material-symbols-outlined animate-spin text-lg">autorenew</span>
          ) : (
            "Create"
          )}
        </button>
      </form>
    </div>
  );
}
