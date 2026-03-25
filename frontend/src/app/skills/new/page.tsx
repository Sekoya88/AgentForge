"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";

type SkillType = "code" | "instruction";

export default function NewSkillPage() {
  const router = useRouter();
  const [skillType, setSkillType] = useState<SkillType>("code");
  const [name, setName] = useState("echo_tool");
  const [description, setDescription] = useState("");
  const [source, setSource] = useState(
    "def run(x: str) -> str:\n    return x\n",
  );
  const [instructions, setInstructions] = useState("");
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
      setSkillType("code");
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
          description: description || null,
          skill_type: skillType,
          source_code: skillType === "code" ? source : "",
          instructions: skillType === "instruction" ? instructions : null,
          parameters_schema: {},
          permissions: skillType === "code" ? ["read"] : [],
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
        &larr; Skills
      </Link>
      <span className="af-kicker mb-2 block">[ NEW SKILL ]</span>
      <h1 className="mb-8 font-sans text-3xl font-bold text-white">
        Register <span className="af-serif-italic text-af-primary">module</span>
      </h1>

      {/* Skill type toggle */}
      <div className="mb-6 flex gap-2">
        <button
          type="button"
          onClick={() => setSkillType("code")}
          className={`rounded-lg px-5 py-2 text-sm font-medium transition-all ${
            skillType === "code"
              ? "bg-af-primary text-black"
              : "border border-af-border bg-af-surface-container text-af-muted hover:text-white"
          }`}
        >
          <span className="material-symbols-outlined mr-1 align-middle text-base">code</span>
          Code Skill
        </button>
        <button
          type="button"
          onClick={() => setSkillType("instruction")}
          className={`rounded-lg px-5 py-2 text-sm font-medium transition-all ${
            skillType === "instruction"
              ? "bg-af-primary text-black"
              : "border border-af-border bg-af-surface-container text-af-muted hover:text-white"
          }`}
        >
          <span className="material-symbols-outlined mr-1 align-middle text-base">description</span>
          Instruction Skill
        </button>
      </div>

      {/* AI Generation (code skills only) */}
      {skillType === "code" && (
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
      )}

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
            Description
          </label>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="af-input"
            placeholder="What does this skill do?"
          />
        </div>

        {skillType === "code" ? (
          <div>
            <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Source Code (Python)
            </label>
            <p className="mb-2 text-xs text-af-muted">
              Must define a <code className="font-mono text-af-primary">run(x: str) -&gt; str</code> function.
            </p>
            <textarea
              value={source}
              onChange={(e) => setSource(e.target.value)}
              rows={10}
              className="af-input resize-y font-mono text-sm"
            />
          </div>
        ) : (
          <div>
            <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Instructions (Natural Language)
            </label>
            <p className="mb-2 text-xs text-af-muted">
              Write instructions the agent will follow. These are injected into the LLM system prompt.
            </p>
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              rows={12}
              placeholder={"You are a specialist in...\n\nWhen the user provides text:\n1. ...\n2. ...\n3. ..."}
              className="af-input resize-y text-sm leading-relaxed"
            />
          </div>
        )}

        {error && <p className="text-sm text-af-error">{error}</p>}
        <button
          type="button"
          disabled={busy}
          onClick={submit}
          className="af-btn-primary flex w-full items-center justify-center gap-2 py-3 text-sm disabled:opacity-50"
        >
          {busy ? (
            <span className="material-symbols-outlined animate-spin text-lg">autorenew</span>
          ) : (
            "Create"
          )}
        </button>
      </div>
    </ToolShell>
  );
}
