"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";

type Source = { title: string; chunk_count: number };

export default function KnowledgePage() {
  const router = useRouter();
  const [sources, setSources] = useState<Source[] | null>(null);
  const [title, setTitle] = useState("Handbook");
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api<Source[]>("/api/v1/knowledge/sources");
      setSources(data);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Failed to load sources");
    }
  }, [router]);

  useEffect(() => {
    void load();
  }, [load]);

  async function ingest() {
    setBusy(true);
    setError(null);
    try {
      await api("/api/v1/knowledge/ingest", {
        method: "POST",
        body: JSON.stringify({ title, text }),
      });
      setText("");
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Ingest failed");
    } finally {
      setBusy(false);
    }
  }

  async function removeSource(t: string) {
    setError(null);
    try {
      await api(`/api/v1/knowledge/sources/${encodeURIComponent(t)}`, { method: "DELETE" });
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  return (
    <ToolShell active="knowledge">
      <header className="mb-10">
        <span className="af-kicker mb-2 block text-af-primary">[ KNOWLEDGE ]</span>
        <h1 className="font-sans text-3xl font-bold text-white md:text-4xl">
          RAG <span className="af-serif-italic text-af-primary">corpus</span>
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-af-muted">
          Ingest text; chunks are embedded with OpenAI <code className="text-af-muted-dim">text-embedding-3-small</code>{" "}
          (requires <code className="text-af-muted-dim">OPENAI_API_KEY</code> on the API). Use a tool node with{" "}
          <code className="text-af-muted-dim">tool_name: &quot;retrieve&quot;</code> and optional{" "}
          <code className="text-af-muted-dim">top_k</code> in <code className="text-af-muted-dim">config</code>.
        </p>
      </header>

      <div className="af-card mb-10 max-w-3xl space-y-4 p-6">
        <h2 className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">Ingest</h2>
        <div>
          <label className="mb-1 block text-xs text-af-muted">Title</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="af-input font-mono text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-af-muted">Text</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            placeholder="Paste documentation, policies, FAQs…"
            className="af-input resize-y font-mono text-sm"
          />
        </div>
        {error && <p className="text-sm text-af-error">{error}</p>}
        <button
          type="button"
          disabled={busy || !text.trim()}
          onClick={() => void ingest()}
          className="af-btn-primary px-6 py-2 text-sm disabled:opacity-50"
        >
          {busy ? "Indexing…" : "Index text"}
        </button>
      </div>

      <div className="max-w-3xl">
        <h2 className="mb-4 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">Sources</h2>
        {sources && sources.length === 0 && (
          <p className="text-sm text-af-muted">No indexed sources yet.</p>
        )}
        {sources && sources.length > 0 && (
          <ul className="space-y-3">
            {sources.map((s) => (
              <li
                key={s.title}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-af-border/40 bg-af-surface-container px-4 py-3"
              >
                <div>
                  <span className="font-mono text-sm text-white">{s.title}</span>
                  <span className="ml-2 text-xs text-af-muted">({s.chunk_count} chunks)</span>
                </div>
                <button
                  type="button"
                  onClick={() => void removeSource(s.title)}
                  className="text-xs text-af-error hover:underline"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="mt-10 text-xs text-af-muted">
        <Link href="/agents/new" className="text-af-primary hover:underline">
          New agent
        </Link>{" "}
        → add a <code className="text-af-muted-dim">tool</code> node with{" "}
        <code className="text-af-muted-dim">retrieve</code> after an LLM that asks a question.
      </p>
    </ToolShell>
  );
}
