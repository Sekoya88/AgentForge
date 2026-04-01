"use client";

import { useEffect, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";
import { consumeSsePath } from "@/lib/sse";

type SkillListItem = { id: string; name: string; description: string | null };

type SkillDetail = SkillListItem & {
  skill_type: string;
  source_code: string;
};

export default function SandboxPage() {
  const [code, setCode] = useState("print(2 + 2)");
  const [out, setOut] = useState("");
  const [lines, setLines] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [skills, setSkills] = useState<SkillListItem[]>([]);
  const [skillPick, setSkillPick] = useState("");
  const [skillDetail, setSkillDetail] = useState<SkillDetail | null>(null);
  const [skillBusy, setSkillBusy] = useState(false);
  const [validateMsg, setValidateMsg] = useState<string | null>(null);
  const [validateBusy, setValidateBusy] = useState(false);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const rows = await api<SkillListItem[]>("/api/v1/skills");
        if (!c) setSkills(rows);
      } catch {
        if (!c) setSkills([]);
      }
    })();
    return () => {
      c = true;
    };
  }, []);

  useEffect(() => {
    if (!skillPick) {
      setSkillDetail(null);
      return;
    }
    let c = false;
    (async () => {
      setSkillBusy(true);
      setValidateMsg(null);
      try {
        const d = await api<SkillDetail>(`/api/v1/skills/${skillPick}`);
        if (!c) setSkillDetail(d);
      } catch (e) {
        if (!c) {
          setSkillDetail(null);
          setErr(e instanceof ApiError ? e.message : "Failed to load skill");
        }
      } finally {
        if (!c) setSkillBusy(false);
      }
    })();
    return () => {
      c = true;
    };
  }, [skillPick]);

  async function run(sync: boolean) {
    setErr(null);
    setOut("");
    setLines([]);
    setBusy(true);
    try {
      if (sync) {
        const res = await api<{
          job_id: string;
          exit_code: number | null;
          stdout: string;
          stderr: string;
        }>("/api/v1/sandbox/run", {
          method: "POST",
          body: JSON.stringify({
            code,
            language: "python",
            run_async: false,
          }),
        });
        const outStr = `${res.stdout}\n${res.stderr}`.trim();
        if (res.exit_code !== 0 && res.exit_code !== null) {
          setOut(outStr + `\n\n[Exited with code ${res.exit_code}]`);
        } else {
          setOut(outStr);
        }
      } else {
        const res = await api<{ job_id: string }>("/api/v1/sandbox/run", {
          method: "POST",
          body: JSON.stringify({
            code,
            language: "python",
            run_async: true,
          }),
        });
        const acc: string[] = [];
        await consumeSsePath(`/api/v1/sandbox/stream/${res.job_id}`, (ev, data) => {
          acc.push(`${ev}: ${data}`);
          setLines([...acc]);
        });
      }
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  async function validateSelectedSkill() {
    if (!skillPick) return;
    setValidateBusy(true);
    setValidateMsg(null);
    try {
      const res = await api<{ valid: boolean; message: string }>(
        `/api/v1/skills/${skillPick}/validate`,
        { method: "POST" },
      );
      setValidateMsg(res.valid ? `Valid: ${res.message}` : `Invalid: ${res.message}`);
    } catch (e) {
      setValidateMsg(e instanceof ApiError ? e.message : "Validate failed");
    } finally {
      setValidateBusy(false);
    }
  }

  function loadSkillIntoEditor() {
    if (!skillDetail?.source_code) return;
    setCode(skillDetail.source_code);
    setValidateMsg(null);
  }

  return (
    <ToolShell active="sandbox">
      <header className="mb-8 space-y-2">
        <div className="flex items-center gap-3">
          <span className="rounded border border-af-primary/20 bg-af-primary/10 px-2 py-0.5 text-[10px] font-bold tracking-[0.2em] text-af-primary">
            [ PLAYGROUND ]
          </span>
          <div className="h-px flex-1 bg-gradient-to-r from-af-primary/20 to-transparent" />
        </div>
        <h1 className="font-sans text-3xl font-bold tracking-tight text-white md:text-4xl">
          Skill <span className="af-serif-italic text-af-primary">playground</span>
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-af-muted">
          Pick a skill to inspect, validate server-side, or load its source into the Python sandbox.
          Async runs stream Redis-backed events over SSE.
        </p>
      </header>

      <div className="mb-6 flex items-start gap-4 rounded-r-xl border-l-4 border-af-error/50 bg-af-error/10 p-4">
        <span className="material-symbols-outlined text-af-error">report</span>
        <div>
          <h4 className="mb-1 text-xs font-bold uppercase tracking-wider text-af-error">
            Safety protocols
          </h4>
          <p className="text-xs leading-relaxed text-af-muted">
            Sandbox execution is isolated; throttle and quotas apply in production. Skill validation
            does not execute arbitrary payloads against your data.
          </p>
        </div>
      </div>

      <div className="mb-6 af-card space-y-4 p-4">
        <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
          Your skills
        </p>
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
          <label className="block min-w-[12rem] flex-1">
            <span className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Skill
            </span>
            <select
              value={skillPick}
              onChange={(e) => setSkillPick(e.target.value)}
              className="af-input w-full text-sm"
            >
              <option value="">— Select —</option>
              {skills.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={!skillPick || validateBusy}
            onClick={() => void validateSelectedSkill()}
            className="rounded-lg border border-af-border px-4 py-2 text-xs font-bold text-af-on-surface transition-colors hover:bg-white/5 disabled:opacity-50"
          >
            {validateBusy ? "Validating…" : "Validate skill"}
          </button>
          <button
            type="button"
            disabled={!skillDetail?.source_code}
            onClick={loadSkillIntoEditor}
            className="af-btn-primary px-4 py-2 text-xs disabled:opacity-50"
          >
            Load source into editor
          </button>
        </div>
        {skills.length === 0 && (
          <div className="text-center py-4 space-y-2">
            <p className="text-xs text-af-muted">Aucun skill trouvé.</p>
            <button
              type="button"
              onClick={async () => {
                await api("/api/v1/skills/seed-defaults", { method: "POST" });
                const rows = await api<SkillListItem[]>("/api/v1/skills");
                setSkills(rows);
              }}
              className="text-xs border border-af-primary/40 text-af-primary px-3 py-1.5 rounded hover:bg-af-primary/10"
            >
              + Installer les skills par défaut
            </button>
          </div>
        )}
        {skillBusy && <p className="text-xs text-af-muted-dim">Loading skill…</p>}
        {skillDetail && !skillBusy && (
          <div className="rounded-lg border border-af-border/40 bg-af-surface-void/50 p-3 text-xs text-af-muted">
            <p className="font-mono text-af-primary">{skillDetail.name}</p>
            {skillDetail.description && <p className="mt-1 text-af-muted-dim">{skillDetail.description}</p>}
            <p className="mt-1 text-[10px] uppercase text-af-muted-dim">Type: {skillDetail.skill_type}</p>
          </div>
        )}
        {validateMsg && (
          <p className="text-xs text-af-muted whitespace-pre-wrap" role="status">
            {validateMsg}
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        <div className="flex flex-col overflow-hidden rounded-xl border border-af-border bg-af-surface-container shadow-2xl xl:col-span-8">
          <div className="flex h-10 items-center justify-between border-b border-af-border/80 bg-af-surface-high/50 px-4">
            <div className="flex items-center gap-2">
              <div className="flex gap-1.5">
                <div className="h-2.5 w-2.5 rounded-full bg-af-error/40" />
                <div className="h-2.5 w-2.5 rounded-full bg-af-secondary/40" />
                <div className="h-2.5 w-2.5 rounded-full bg-af-tertiary/40" />
              </div>
              <span className="ml-4 text-[10px] font-bold tracking-widest text-af-muted-dim uppercase">
                playground.py
              </span>
            </div>
            <span className="text-xs text-af-muted-dim">Python 3</span>
          </div>
          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            rows={14}
            className="min-h-[320px] flex-1 resize-y border-0 bg-af-surface-void p-6 font-mono text-sm leading-6 text-af-on-surface focus:ring-0"
          />
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-af-border/80 p-4">
            <span className="flex items-center gap-1 text-[10px] text-af-tertiary">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-af-tertiary" />
              Ready
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => run(true)}
                className="af-btn-primary flex items-center justify-center gap-2 px-5 py-2 text-xs disabled:opacity-50 min-w-[100px]"
              >
                {busy ? <span className="material-symbols-outlined animate-spin text-sm">autorenew</span> : "Run sync"}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => run(false)}
                className="rounded-lg border border-af-border px-5 py-2 text-xs font-bold text-af-on-surface transition-colors hover:bg-white/5 disabled:opacity-50 flex items-center justify-center gap-2 min-w-[120px]"
              >
                {busy ? <span className="material-symbols-outlined animate-spin text-sm">autorenew</span> : "Run + stream"}
              </button>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-6 xl:col-span-4">
          <div className="flex flex-1 flex-col overflow-hidden rounded-xl border border-af-border bg-af-surface-high/30">
            <div className="flex items-center justify-between border-b border-af-border/80 px-4 py-2">
              <span className="text-[10px] font-bold uppercase text-af-muted">Output</span>
            </div>
            <div className="max-h-[280px] flex-1 overflow-y-auto p-4 font-mono text-[11px] text-af-secondary xl:max-h-none">
              {err && <p className="text-af-error">{err}</p>}
              {out && <pre className="whitespace-pre-wrap text-af-muted">{out}</pre>}
              {lines.length > 0 && (
                <pre className="mt-2 whitespace-pre-wrap text-af-muted">{lines.join("\n")}</pre>
              )}
              {!err && !out && lines.length === 0 && (
                <span className="text-af-muted-dim">Awaiting run…</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </ToolShell>
  );
}
