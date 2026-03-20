"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";

export default function NewSkillPage() {
  const router = useRouter();
  const [name, setName] = useState("echo_tool");
  const [source, setSource] = useState(
    "def run(x: str) -> str:\n    return x\n",
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [prompt, setPrompt] = useState("");

  async function onGenerate() {
    if (!prompt.trim()) return;
    setGenerating(true);
    setError(null);
    try {
      const res = await api<{ name: string; source_code: string }>(
        "/api/v1/generate/skill",
        {
          method: "POST",
          body: JSON.stringify({ prompt }),
        },
      );
      setName(res.name);
      setSource(res.source_code);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Generate failed");
    } finally {
      setGenerating(false);
    }
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api("/api/v1/skills", {
        method: "POST",
        body: JSON.stringify({
          name,
          source_code: source,
          parameters_schema: {},
          permissions: ["read"],
          is_public: false,
        }),
      });
      router.push("/skills");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ToolShell active="skills">
      <Link
        href="/skills"
        className="mb-6 inline-block text-sm text-af-muted hover:text-af-primary"
      >
        ← Skills
      </Link>
      <span className="af-kicker mb-2 block">[ NEW SKILL ]</span>
      <h1 className="mb-8 font-sans text-3xl font-bold text-white">
        Register <span className="af-serif-italic text-af-primary">module</span>
      </h1>

      <div className="af-card max-w-2xl mb-8 space-y-4 p-6 border-af-primary/20 bg-af-primary/5">
        <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-primary">
          AI Generation (Natural Language)
        </label>
        <div className="flex gap-2">
          <input
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="E.g. A tool that fetches the weather using wttr.in..."
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

      <div className="af-card max-w-2xl space-y-6 p-8">
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
            Source (Python stub)
          </label>
          <textarea
            value={source}
            onChange={(e) => setSource(e.target.value)}
            rows={10}
            className="af-input resize-y font-mono text-sm"
          />
        </div>
        {error && <p className="text-sm text-af-error">{error}</p>}
        <button
          type="button"
          disabled={busy}
          onClick={submit}
          className="af-btn-primary w-full justify-center py-3 text-sm disabled:opacity-50"
        >
          {busy ? "Saving…" : "Create"}
        </button>
      </div>
    </ToolShell>
  );
}
