"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";

type Skill = {
  id: string;
  name: string;
  description: string | null;
  skill_type: string;
  source_code: string;
  instructions: string | null;
  parameters_schema: Record<string, unknown>;
  permissions: string[];
  is_public: boolean;
  security_validated: boolean;
};

type ValidateResult = {
  valid: boolean;
  message: string;
};

export default function SkillDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [skill, setSkill] = useState<Skill | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [skillType, setSkillType] = useState<string>("code");
  const [sourceCode, setSourceCode] = useState("");
  const [instructions, setInstructions] = useState("");
  const [isPublic, setIsPublic] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validateResult, setValidateResult] = useState<ValidateResult | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const s = await api<Skill>(`/api/v1/skills/${id}`);
        if (!c) {
          setSkill(s);
          setName(s.name);
          setDescription(s.description ?? "");
          setSkillType(s.skill_type || "code");
          setSourceCode(s.source_code);
          setInstructions(s.instructions ?? "");
          setIsPublic(s.is_public);
        }
      } catch (e) {
        if (!c) {
          if (e instanceof ApiError && e.status === 401) router.push("/login");
          else setError(e instanceof Error ? e.message : "Load failed");
        }
      }
    })();
    return () => { c = true; };
  }, [id, router]);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const s = await api<Skill>(`/api/v1/skills/${id}`, {
        method: "PUT",
        body: JSON.stringify({
          name,
          description: description || null,
          skill_type: skillType,
          source_code: skillType === "code" ? sourceCode : "",
          instructions: skillType === "instruction" ? instructions : null,
          is_public: isPublic,
        }),
      });
      setSkill(s);
      setValidateResult(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function validate() {
    setValidating(true);
    setValidateResult(null);
    try {
      const r = await api<ValidateResult>(`/api/v1/skills/${id}/validate`, {
        method: "POST",
      });
      setValidateResult(r);
    } catch (e) {
      setValidateResult({ valid: false, message: e instanceof Error ? e.message : "Validation failed" });
    } finally {
      setValidating(false);
    }
  }

  async function del() {
    if (!confirm("Delete this skill permanently?")) return;
    setDeleting(true);
    try {
      await api(`/api/v1/skills/${id}`, { method: "DELETE" });
      router.push("/skills");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
      setDeleting(false);
    }
  }

  if (error && !skill) return <p className="px-4 text-af-error">{error}</p>;
  if (!skill) return <p className="px-4 text-af-muted">Loading...</p>;

  return (
    <ToolShell active="skills">
      <div className="mx-auto max-w-3xl">
        <Link href="/skills" className="mb-6 inline-block text-sm text-af-muted hover:text-af-primary">
          &larr; Skills
        </Link>
        <div className="mb-2 flex items-center gap-3">
          <span className="af-kicker text-af-primary">[ SKILL ]</span>
          <span className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase ${
            skillType === "instruction"
              ? "bg-violet-500/20 text-violet-400"
              : "bg-indigo-500/20 text-indigo-400"
          }`}>
            {skillType}
          </span>
        </div>
        <h1 className="mb-8 font-sans text-3xl font-bold tracking-tight text-white md:text-4xl">
          {skill.name}
        </h1>

        <div className="space-y-6">
          <div className="af-card space-y-5 p-6">
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
                placeholder="Optional description..."
              />
            </div>

            {/* Skill type toggle */}
            <div>
              <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                Skill Type
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setSkillType("code")}
                  className={`rounded-lg px-4 py-1.5 text-xs font-medium transition-all ${
                    skillType === "code"
                      ? "bg-af-primary text-black"
                      : "border border-af-border text-af-muted hover:text-white"
                  }`}
                >
                  Code
                </button>
                <button
                  type="button"
                  onClick={() => setSkillType("instruction")}
                  className={`rounded-lg px-4 py-1.5 text-xs font-medium transition-all ${
                    skillType === "instruction"
                      ? "bg-af-primary text-black"
                      : "border border-af-border text-af-muted hover:text-white"
                  }`}
                >
                  Instruction
                </button>
              </div>
            </div>

            {/* Conditional editor based on skill type */}
            {skillType === "code" ? (
              <div>
                <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                  Source code (Python)
                </label>
                <textarea
                  rows={16}
                  value={sourceCode}
                  onChange={(e) => setSourceCode(e.target.value)}
                  className="af-input min-h-[280px] resize-y font-mono text-xs leading-relaxed"
                />
              </div>
            ) : (
              <div>
                <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                  Instructions (Natural Language)
                </label>
                <p className="mb-2 text-xs text-af-muted">
                  These instructions are injected into the agent&apos;s system prompt during execution.
                </p>
                <textarea
                  rows={16}
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  placeholder={"You are a specialist in...\n\nWhen the user provides text:\n1. ...\n2. ...\n3. ..."}
                  className="af-input min-h-[280px] resize-y text-sm leading-relaxed"
                />
              </div>
            )}

            <label className="flex items-center gap-2 text-sm text-af-muted">
              <input
                type="checkbox"
                checked={isPublic}
                onChange={(e) => setIsPublic(e.target.checked)}
                className="rounded border-af-border"
              />
              Public (visible to other users)
            </label>
          </div>

          {/* Validation result */}
          {validateResult && (
            <div
              className={`rounded-xl border p-4 text-sm ${
                validateResult.valid
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                  : "border-red-500/30 bg-red-500/10 text-red-400"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-sm">
                  {validateResult.valid ? "check_circle" : "error"}
                </span>
                {validateResult.message}
              </div>
            </div>
          )}

          {error && <p className="text-sm text-af-error">{error}</p>}

          {/* Actions */}
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={save}
              disabled={saving}
              className="af-btn-primary flex items-center gap-2 px-6 py-2.5 text-sm disabled:opacity-50"
            >
              {saving ? (
                <>
                  <span className="material-symbols-outlined animate-spin text-sm">autorenew</span>
                  Saving...
                </>
              ) : (
                "Save"
              )}
            </button>
            <button
              type="button"
              onClick={validate}
              disabled={validating}
              className="rounded-lg border border-af-primary/40 bg-af-primary/10 px-6 py-2.5 text-sm text-af-primary transition-colors hover:bg-af-primary/20 disabled:opacity-50"
            >
              {validating ? "Validating..." : "Validate"}
            </button>
            <button
              type="button"
              onClick={del}
              disabled={deleting}
              className="rounded-lg border border-red-500/30 bg-red-500/10 px-6 py-2.5 text-sm text-red-400 transition-colors hover:bg-red-500/20 disabled:opacity-50"
            >
              Delete
            </button>
          </div>

          {/* Metadata */}
          <div className="af-card p-6">
            <p className="mb-3 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Metadata
            </p>
            <div className="space-y-2 text-xs text-af-muted">
              <p>
                <span className="text-af-muted-dim">ID:</span>{" "}
                <code className="font-mono">{skill.id}</code>
              </p>
              <p>
                <span className="text-af-muted-dim">Type:</span>{" "}
                <span className={skillType === "instruction" ? "text-violet-400" : "text-indigo-400"}>
                  {skillType}
                </span>
              </p>
              <p>
                <span className="text-af-muted-dim">Security validated:</span>{" "}
                <span className={skill.security_validated ? "text-emerald-400" : "text-amber-400"}>
                  {skill.security_validated ? "Yes" : "No"}
                </span>
              </p>
              <p>
                <span className="text-af-muted-dim">Permissions:</span>{" "}
                {skill.permissions.length > 0 ? skill.permissions.join(", ") : "none"}
              </p>
            </div>
          </div>
        </div>
      </div>
    </ToolShell>
  );
}
