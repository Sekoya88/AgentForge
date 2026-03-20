"use client";

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

export default function NewAgentPage() {
  const router = useRouter();
  const [name, setName] = useState("My agent");
  const [graphJson, setGraphJson] = useState(DEFAULT_GRAPH);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
      const agent = await api<{ id: string }>("/api/v1/agents", {
        method: "POST",
        body: JSON.stringify({
          name,
          description: null,
          graph_definition,
          model_config: {
            provider: "gemini",
            model: "gemini-2.5-pro",
            temperature: 0.2,
          },
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
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">New agent</h1>
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="mb-1 block text-sm text-neutral-400">Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm text-neutral-400">graph_definition (JSON)</label>
          <textarea
            rows={14}
            value={graphJson}
            onChange={(e) => setGraphJson(e.target.value)}
            className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 font-mono text-xs"
          />
        </div>
        {error && <p className="text-sm text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-cyan-500 px-4 py-2 text-sm font-medium text-black disabled:opacity-50"
        >
          {loading ? "…" : "Create"}
        </button>
      </form>
    </div>
  );
}
