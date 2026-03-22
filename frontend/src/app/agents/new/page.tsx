"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

const DEFAULT_GRAPH = `{
  "nodes": [
    { "id": "n1", "type": "llm", "config": { "prompt": "You are helpful." } },
    { "id": "n2", "type": "tool", "config": { "tool_name": "echo" } }
  ],
  "edges": [ { "from": "n1", "to": "n2" } ],
  "entry_point": "n1"
}`;

const PROVIDERS = [
  { value: "mock", label: "Mock (offline echo) — recommended for dev" },
  { value: "openai", label: "OpenAI (needs OPENAI_API_KEY on API)" },
  { value: "gemini", label: "Gemini (needs GOOGLE_API_KEY on API)" },
] as const;

export default function NewAgentPage() {
  const router = useRouter();
  const [name, setName] = useState("My agent");
  const [provider, setProvider] =
    useState<(typeof PROVIDERS)[number]["value"]>("mock");
  const [graphJson, setGraphJson] = useState(DEFAULT_GRAPH);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [prompt, setPrompt] = useState("");

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
      if (res.model_config?.provider) {
        const found = PROVIDERS.find(
          (p) => p.value === res.model_config.provider,
        );
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
      const model_config =
        provider === "mock"
          ? { provider: "mock", temperature: 0.2 }
          : provider === "openai"
            ? { provider: "openai", model: "gpt-5.4-mini", temperature: 0.2 }
            : { provider: "gemini", model: "gemini-2.5-pro", temperature: 0.2 };

      const agent = await api<{ id: string }>("/api/v1/agents", {
        method: "POST",
        body: JSON.stringify({
          name,
          description: null,
          graph_definition,
          model_config,
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
      <Link
        href="/agents"
        className="mb-6 inline-block text-sm text-af-muted hover:text-af-primary"
      >
        ← Agents
      </Link>
      <span className="af-kicker mb-2 block">[ NEW AGENT ]</span>
      <h1 className="mb-8 font-sans text-3xl font-bold tracking-tight text-white md:text-4xl">
        Initialize <span className="af-serif-italic text-af-primary">unit</span>
      </h1>

      <div className="af-card mb-8 space-y-4 p-6 border-af-primary/20 bg-af-primary/5">
        <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-primary">
          AI Generation (Natural Language)
        </label>
        <div className="flex gap-2">
          <input
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="E.g. A research agent that searches the web and summarizes findings..."
            className="af-input flex-1 font-mono text-sm"
          />
          <button
            type="button"
            onClick={onGenerate}
            disabled={generating || !prompt.trim()}
            className="af-btn-primary px-6 py-2 text-sm disabled:opacity-50"
          >
            {generating ? "Generating..." : "Generate"}
          </button>
        </div>
      </div>

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
        <div>
          <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
            LLM provider
          </label>
          <select
            value={provider}
            onChange={(e) =>
              setProvider(e.target.value as (typeof PROVIDERS)[number]["value"])
            }
            className="af-input font-mono text-sm"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
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
          className="af-btn-primary w-full justify-center py-3 text-sm disabled:opacity-50"
        >
          {loading ? "…" : "Create"}
        </button>
      </form>
    </div>
  );
}
