"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";
import { EmptyState } from "@/components/ui/EmptyState";

type Source = { title: string; chunk_count: number };

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function KnowledgePage() {
  const router = useRouter();
  const [sources, setSources] = useState<Source[] | null>(null);
  const [title, setTitle] = useState("Handbook");
  const [text, setText] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [urlBusy, setUrlBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const data = await api<Source[]>("/api/v1/knowledge/sources");
      setSources(data);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Failed to load sources");
    }
  }, [router]);

  useEffect(() => { void load(); }, [load]);

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

  async function uploadFile(file: File) {
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const token = localStorage.getItem("access_token");
      const res = await fetch(`${BASE}/api/v1/knowledge/upload`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Upload failed (${res.status})`);
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) void uploadFile(f);
    e.target.value = "";
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) void uploadFile(f);
  }

  async function ingestUrl() {
    if (!urlInput.trim()) return;
    setUrlBusy(true);
    setError(null);
    try {
      await api("/api/v1/knowledge/ingest-url", {
        method: "POST",
        body: JSON.stringify({ url: urlInput.trim() }),
      });
      setUrlInput("");
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "URL ingest failed");
    } finally {
      setUrlBusy(false);
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
          Ingest text or upload files (.txt, .md, .csv, .pdf). Chunks are embedded with OpenAI{" "}
          <code className="text-af-muted-dim">text-embedding-3-small</code>.
          Use a tool node with <code className="text-af-muted-dim">tool_name: &quot;retrieve&quot;</code>.
        </p>
      </header>

      {/* File upload */}
      <div
        className={[
          "af-card mb-6 max-w-3xl p-6 transition-all",
          dragOver ? "border-af-primary bg-af-primary/10" : "",
        ].join(" ")}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <h2 className="mb-3 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
          Upload file
        </h2>
        <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-af-border/60 p-8">
          <span className="material-symbols-outlined text-3xl text-af-muted">upload_file</span>
          <p className="text-sm text-af-muted">
            {uploading ? "Uploading..." : "Drag & drop a file here, or"}
          </p>
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="rounded-lg border border-af-primary/40 bg-af-primary/10 px-4 py-2 text-sm text-af-primary transition-colors hover:bg-af-primary/20 disabled:opacity-50"
          >
            Browse files
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".txt,.md,.csv,.pdf"
            onChange={onFileChange}
            className="hidden"
          />
          <p className="text-xs text-af-muted-dim">.txt, .md, .csv, .pdf</p>
        </div>
      </div>

      {/* URL ingest */}
      <div className="af-card mb-6 max-w-3xl p-6">
        <h2 className="mb-3 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
          Ingest URL
        </h2>
        <div className="flex gap-2">
          <input
            type="url"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") void ingestUrl(); }}
            placeholder="https://docs.example.com/getting-started"
            className="af-input flex-1 text-sm"
            disabled={urlBusy}
          />
          <button
            type="button"
            disabled={urlBusy || !urlInput.trim()}
            onClick={() => void ingestUrl()}
            className="af-btn-primary whitespace-nowrap px-4 py-2 text-sm disabled:opacity-50"
          >
            {urlBusy ? "Fetching…" : "Ingest URL"}
          </button>
        </div>
        <p className="mt-2 text-xs text-af-muted-dim">
          Fetches the page, strips HTML, and indexes the text. Works with docs, READMEs, and articles.
        </p>
      </div>

      {/* Text ingest */}
      <div className="af-card mb-10 max-w-3xl space-y-4 p-6">
        <h2 className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">Paste text</h2>
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
            rows={8}
            placeholder="Paste documentation, policies, FAQs..."
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
          {busy ? "Indexing..." : "Index text"}
        </button>
      </div>

      {/* Sources */}
      <div className="max-w-3xl">
        <h2 className="mb-4 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
          Indexed sources ({sources?.length ?? 0})
        </h2>
        {sources && sources.length === 0 && (
          <EmptyState
            icon={<span className="material-symbols-outlined text-3xl">menu_book</span>}
            title="No knowledge sources yet"
            description="Upload a file or paste text above to build your RAG corpus. Chunks are embedded and searchable by any agent with a Retrieve node."
          />
        )}
        {sources && sources.length > 0 && (
          <ul className="space-y-3">
            {sources.map((s) => (
              <li
                key={s.title}
                className="af-card-interactive flex flex-wrap items-center justify-between gap-2 rounded-lg border border-af-border/40 bg-af-surface-container px-4 py-3"
              >
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm text-af-muted">description</span>
                  <span className="font-mono text-sm text-white">{s.title}</span>
                  <span className="text-xs text-af-muted">({s.chunk_count} chunks)</span>
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
        <code className="text-af-muted-dim">retrieve</code>.
      </p>
    </ToolShell>
  );
}
