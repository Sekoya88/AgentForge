"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api, compareAgentExecutions, type AgentCompareResponse } from "@/lib/api";
import { consumeSsePath } from "@/lib/sse";

type SkillListItem = { id: string; name: string; description: string | null };

type SkillTemplateRow = {
  name: string;
  description: string | null;
  skill_type: string;
  category?: string;
};

type SkillDetail = SkillListItem & {
  skill_type: string;
  source_code: string;
};

type AgentRow = { id: string; name: string };

type Pane = "l" | "r";

const DEFAULT_PY = "print(2 + 2)";

export default function SandboxPage() {
  const [codeL, setCodeL] = useState(DEFAULT_PY);
  const [codeR, setCodeR] = useState(DEFAULT_PY);
  const [outL, setOutL] = useState("");
  const [outR, setOutR] = useState("");
  const [linesL, setLinesL] = useState<string[]>([]);
  const [linesR, setLinesR] = useState<string[]>([]);
  const [errL, setErrL] = useState<string | null>(null);
  const [errR, setErrR] = useState<string | null>(null);
  const [busyL, setBusyL] = useState(false);
  const [busyR, setBusyR] = useState(false);
  const [skills, setSkills] = useState<SkillListItem[]>([]);
  const [skillPick, setSkillPick] = useState("");
  const [skillDetail, setSkillDetail] = useState<SkillDetail | null>(null);
  const [skillBusy, setSkillBusy] = useState(false);
  const [validateMsg, setValidateMsg] = useState<string | null>(null);
  const [validateBusy, setValidateBusy] = useState(false);
  const [templates, setTemplates] = useState<SkillTemplateRow[]>([]);
  const [installing, setInstalling] = useState<string | null>(null);
  const [catalogErr, setCatalogErr] = useState<string | null>(null);
  const [skillLoadErr, setSkillLoadErr] = useState<string | null>(null);
  const [compareAgents, setCompareAgents] = useState<AgentRow[]>([]);
  const [compareAgentId, setCompareAgentId] = useState("");
  const [compareMsg, setCompareMsg] = useState("Réponds en une phrase.");
  const [compareJsonA, setCompareJsonA] = useState('{"temperature":0.2}');
  const [compareJsonB, setCompareJsonB] = useState('{"temperature":0.9}');
  const [compareBusy, setCompareBusy] = useState(false);
  const [compareRes, setCompareRes] = useState<AgentCompareResponse | null>(null);
  const [compareErr, setCompareErr] = useState<string | null>(null);

  const refreshUserSkills = useCallback(async () => {
    try {
      const rows = await api<SkillListItem[]>("/api/v1/skills");
      setSkills(rows);
    } catch {
      setSkills([]);
    }
  }, []);

  useEffect(() => {
    void refreshUserSkills();
  }, [refreshUserSkills]);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const rows = await api<AgentRow[]>("/api/v1/agents");
        if (!c) {
          setCompareAgents(rows);
          setCompareAgentId((prev) => prev || (rows[0]?.id ?? ""));
        }
      } catch {
        if (!c) setCompareAgents([]);
      }
    })();
    return () => {
      c = true;
    };
  }, []);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const rows = await api<SkillTemplateRow[]>("/api/v1/skills/templates/list");
        if (!c) setTemplates(rows);
      } catch {
        if (!c) setTemplates([]);
      }
    })();
    return () => {
      c = true;
    };
  }, []);

  const templatesByCategory = useMemo(() => {
    const m = new Map<string, SkillTemplateRow[]>();
    for (const t of templates) {
      const cat = t.category ?? "other";
      const arr = m.get(cat) ?? [];
      arr.push(t);
      m.set(cat, arr);
    }
    return [...m.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [templates]);

  const ownedNames = useMemo(() => new Set(skills.map((s) => s.name)), [skills]);

  async function installTemplate(name: string) {
    setInstalling(name);
    setCatalogErr(null);
    try {
      await api(`/api/v1/skills/templates/${encodeURIComponent(name)}/install`, {
        method: "POST",
      });
      await refreshUserSkills();
    } catch (e) {
      setCatalogErr(
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Install failed",
      );
    } finally {
      setInstalling(null);
    }
  }

  async function runCompare() {
    setCompareErr(null);
    setCompareRes(null);
    if (!compareAgentId.trim()) {
      setCompareErr("Choisis un agent.");
      return;
    }
    let oa: Record<string, unknown>;
    let ob: Record<string, unknown>;
    try {
      oa = JSON.parse(compareJsonA) as Record<string, unknown>;
    } catch {
      setCompareErr("JSON variante A invalide.");
      return;
    }
    try {
      ob = JSON.parse(compareJsonB) as Record<string, unknown>;
    } catch {
      setCompareErr("JSON variante B invalide.");
      return;
    }
    setCompareBusy(true);
    try {
      const res = await compareAgentExecutions(
        compareAgentId,
        compareMsg,
        [
          { label: "A", model_config_override: oa },
          { label: "B", model_config_override: ob },
        ],
        false,
      );
      setCompareRes(res);
    } catch (e) {
      setCompareErr(e instanceof ApiError ? e.message : "Compare failed");
    } finally {
      setCompareBusy(false);
    }
  }

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
          setSkillLoadErr(e instanceof ApiError ? e.message : "Failed to load skill");
        }
      } finally {
        if (!c) setSkillBusy(false);
      }
    })();
    return () => {
      c = true;
    };
  }, [skillPick]);

  async function runSandboxPane(pane: Pane, sync: boolean) {
    const isL = pane === "l";
    const code = isL ? codeL : codeR;
    const setBusy = isL ? setBusyL : setBusyR;
    const setErr = isL ? setErrL : setErrR;
    const setOut = isL ? setOutL : setOutR;
    const setLines = isL ? setLinesL : setLinesR;

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

  function loadSkillIntoPane(which: Pane) {
    if (!skillDetail?.source_code) return;
    setValidateMsg(null);
    if (which === "l") setCodeL(skillDetail.source_code);
    else setCodeR(skillDetail.source_code);
  }

  function copyLeftToRight() {
    setCodeR(codeL);
  }

  function idePane(
    pane: Pane,
    title: string,
    accent: "primary" | "tertiary",
    code: string,
    setCode: (v: string) => void,
    out: string,
    lines: string[],
    err: string | null,
    busy: boolean,
  ) {
    const ring = accent === "primary" ? "ring-af-primary/15" : "ring-af-tertiary/15";
    return (
      <div
        className={`flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-af-border bg-af-surface-container/90 shadow-xl ring-1 ${ring} backdrop-blur-sm`}
      >
        <div className="flex h-10 shrink-0 items-center justify-between border-b border-af-border/80 bg-af-surface-high/60 px-3">
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              <div className="h-2 w-2 rounded-full bg-af-error/50" />
              <div className="h-2 w-2 rounded-full bg-af-secondary/50" />
              <div className="h-2 w-2 rounded-full bg-af-tertiary/50" />
            </div>
            <span className="ml-1 font-mono text-[10px] font-bold tracking-widest text-af-muted-dim uppercase">
              {title}
            </span>
          </div>
          <span className="text-[10px] text-af-muted-dim">Python 3</span>
        </div>
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          rows={10}
          className="min-h-[200px] flex-1 resize-y border-0 bg-af-surface-void/80 p-4 font-mono text-xs leading-relaxed text-af-on-surface focus:ring-0 md:min-h-[260px]"
        />
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t border-af-border/80 bg-af-surface-high/40 px-3 py-2">
          <span className="flex items-center gap-1 text-[10px] text-af-tertiary">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-af-tertiary" />
            Ready
          </span>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              disabled={busy}
              onClick={() => void runSandboxPane(pane, true)}
              className="af-btn-primary px-3 py-1.5 text-[10px] disabled:opacity-50"
            >
              {busy ? <span className="material-symbols-outlined animate-spin text-sm">autorenew</span> : "Run sync"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void runSandboxPane(pane, false)}
              className="rounded-lg border border-af-border px-3 py-1.5 text-[10px] font-bold text-af-on-surface transition-colors hover:bg-white/5 disabled:opacity-50"
            >
              {busy ? <span className="material-symbols-outlined animate-spin text-sm">autorenew</span> : "Stream"}
            </button>
          </div>
        </div>
        <div className="max-h-36 shrink-0 overflow-y-auto border-t border-af-border/60 bg-af-surface-void/50 p-3 font-mono text-[10px] text-af-secondary">
          {err && <p className="text-af-error">{err}</p>}
          {out && <pre className="whitespace-pre-wrap text-af-muted">{out}</pre>}
          {lines.length > 0 && (
            <pre className="mt-1 whitespace-pre-wrap text-af-muted">{lines.join("\n")}</pre>
          )}
          {!err && !out && lines.length === 0 && (
            <span className="text-af-muted-dim">Awaiting run…</span>
          )}
        </div>
      </div>
    );
  }

  return (
    <ToolShell active="sandbox">
      <header className="mb-8 space-y-2">
        <div className="flex items-center gap-3">
          <span className="rounded border border-af-primary/25 bg-gradient-to-r from-af-primary/15 to-af-tertiary/10 px-2 py-0.5 text-[10px] font-bold tracking-[0.2em] text-af-primary">
            [ LAB ]
          </span>
          <div className="h-px flex-1 bg-gradient-to-r from-af-primary/30 via-af-tertiary/20 to-transparent" />
        </div>
        <h1 className="font-sans text-3xl font-bold tracking-tight text-white md:text-4xl">
          Playground <span className="af-serif-italic text-af-tertiary">skills</span>
          <span className="text-af-muted-dim"> · </span>
          <span className="af-serif-italic text-af-primary">A/B agents</span>
        </h1>
        <p className="max-w-3xl text-sm leading-relaxed text-af-muted">
          Deux runners Python côte à côte pour comparer du code skill, plus un banc A/B sur le même
          agent avec des overrides <span className="font-mono text-af-primary">model_config</span>.
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

      <div className="mb-6 af-card space-y-4 p-4 ring-1 ring-white/5">
        <p className="af-kicker">Your skills</p>
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
            onClick={() => loadSkillIntoPane("l")}
            className="af-btn-primary px-4 py-2 text-xs disabled:opacity-50"
          >
            Load → panel A
          </button>
          <button
            type="button"
            disabled={!skillDetail?.source_code}
            onClick={() => loadSkillIntoPane("r")}
            className="rounded-lg border border-af-tertiary/40 px-4 py-2 text-xs font-bold text-af-tertiary transition-colors hover:bg-af-tertiary/10 disabled:opacity-50"
          >
            Load → panel B
          </button>
        </div>
        {skills.length === 0 && (
          <div className="space-y-2 py-4 text-center">
            <p className="text-xs text-af-muted">Aucun skill trouvé.</p>
            <button
              type="button"
              onClick={async () => {
                await api("/api/v1/skills/seed-defaults", { method: "POST" });
                await refreshUserSkills();
              }}
              className="rounded border border-af-primary/40 px-3 py-1.5 text-xs text-af-primary hover:bg-af-primary/10"
            >
              + Installer les skills par défaut
            </button>
          </div>
        )}
        {skillBusy && <p className="text-xs text-af-muted-dim">Loading skill…</p>}
        {skillLoadErr && <p className="text-xs text-af-error">{skillLoadErr}</p>}
        {skillDetail && !skillBusy && (
          <div className="rounded-lg border border-af-border/40 bg-af-surface-void/50 p-3 text-xs text-af-muted">
            <p className="font-mono text-af-primary">{skillDetail.name}</p>
            {skillDetail.description && (
              <p className="mt-1 text-af-muted-dim">{skillDetail.description}</p>
            )}
            <p className="mt-1 text-[10px] uppercase text-af-muted-dim">
              Type: {skillDetail.skill_type}
            </p>
          </div>
        )}
        {validateMsg && (
          <p className="whitespace-pre-wrap text-xs text-af-muted" role="status">
            {validateMsg}
          </p>
        )}
      </div>

      <section className="mb-8 rounded-2xl border border-af-primary/20 bg-gradient-to-br from-af-surface-container/80 via-af-surface-dim/40 to-af-surface-void/60 p-1 shadow-lg ring-1 ring-af-primary/10">
        <div className="rounded-xl bg-af-bg/40 p-4 backdrop-blur-sm md:p-5">
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="af-kicker text-af-primary">Agent A/B lab</p>
              <p className="mt-1 max-w-2xl text-xs text-af-muted">
                Un agent, un message, deux JSON d&apos;override — résultats en deux colonnes.
              </p>
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-3 lg:col-span-2 lg:grid lg:grid-cols-2 lg:gap-4 lg:space-y-0">
              <label className="block lg:col-span-2">
                <span className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                  Agent
                </span>
                <select
                  value={compareAgentId}
                  onChange={(e) => setCompareAgentId(e.target.value)}
                  className="af-input w-full text-sm"
                >
                  {compareAgents.length === 0 && <option value="">— Aucun agent —</option>}
                  {compareAgents.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block lg:col-span-2">
                <span className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                  Message commun
                </span>
                <textarea
                  value={compareMsg}
                  onChange={(e) => setCompareMsg(e.target.value)}
                  rows={2}
                  className="af-input w-full resize-y text-sm"
                />
              </label>
            </div>
            <div className="rounded-xl border border-af-border/60 bg-af-surface-void/40 p-3">
              <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-af-primary">
                Variante A
              </p>
              <textarea
                value={compareJsonA}
                onChange={(e) => setCompareJsonA(e.target.value)}
                rows={6}
                className="af-input min-h-[120px] w-full resize-y font-mono text-xs"
              />
            </div>
            <div className="rounded-xl border border-af-border/60 bg-af-surface-void/40 p-3">
              <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-af-tertiary">
                Variante B
              </p>
              <textarea
                value={compareJsonB}
                onChange={(e) => setCompareJsonB(e.target.value)}
                rows={6}
                className="af-input min-h-[120px] w-full resize-y font-mono text-xs"
              />
            </div>
          </div>
          <button
            type="button"
            disabled={compareBusy || !compareAgentId}
            onClick={() => void runCompare()}
            className="mt-4 af-btn-primary px-5 py-2.5 text-xs disabled:opacity-50"
          >
            {compareBusy ? "Exécution…" : "Lancer la comparaison"}
          </button>
          {compareErr && (
            <p className="mt-2 text-xs text-af-error" role="alert">
              {compareErr}
            </p>
          )}
          {compareRes && (
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <p className="font-mono text-[10px] text-af-muted-dim md:col-span-2">
                compare_group_id: {compareRes.compare_group_id}
              </p>
              {compareRes.executions.map((ex) => {
                const last = ex.output_messages?.filter((m) => m.role === "assistant").pop();
                const text = last?.content ?? "(pas de réponse assistant)";
                return (
                  <div
                    key={ex.id}
                    className="rounded-xl border border-af-border/50 bg-af-surface-high/20 p-4 shadow-inner"
                  >
                    <p className="text-[10px] font-bold uppercase text-af-primary">
                      {ex.compare_label ?? "?"}
                    </p>
                    <p className="mt-1 text-[11px] text-af-muted-dim">status: {ex.status}</p>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-af-on-surface">{text}</p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </section>

      <section className="mb-8">
        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="af-kicker">Dual Python runners</p>
            <p className="text-xs text-af-muted">
              Compare deux snippets (ou charge le même skill dans A et B puis modifie).
            </p>
          </div>
          <button
            type="button"
            onClick={copyLeftToRight}
            className="self-start rounded-lg border border-af-border px-3 py-1.5 text-[10px] font-bold text-af-muted hover:bg-white/5 sm:self-auto"
          >
            Copy A → B
          </button>
        </div>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-stretch">
          {idePane("l", "playground_a.py", "primary", codeL, setCodeL, outL, linesL, errL, busyL)}
          <div className="hidden w-px shrink-0 bg-gradient-to-b from-transparent via-af-border to-transparent lg:block" />
          {idePane("r", "playground_b.py", "tertiary", codeR, setCodeR, outR, linesR, errR, busyR)}
        </div>
      </section>

      <div className="af-card mb-6 max-h-[min(420px,50vh)] overflow-hidden p-4 shadow-lg ring-1 ring-white/5">
        <p className="af-kicker">Catalogue (templates)</p>
        <p className="mt-1 text-xs text-af-muted">
          {templates.length} modèles — installe un skill dans ton compte (auth requise). Déjà présents
          sont grisés.
        </p>
        {catalogErr && <p className="mt-2 text-xs text-af-error">{catalogErr}</p>}
        <div className="mt-3 max-h-[min(320px,40vh)] space-y-4 overflow-y-auto rounded-lg border border-af-border/60 bg-af-surface-dim/20 pr-1">
          {templatesByCategory.map(([cat, items]) => (
            <div key={cat} className="p-2">
              <p className="af-kicker mb-2">{cat}</p>
              <ul className="space-y-2">
                {items.map((t) => {
                  const have = ownedNames.has(t.name);
                  return (
                    <li
                      key={t.name}
                      className="af-hover-lift flex flex-col gap-2 rounded-lg border border-af-border/50 bg-af-surface-void/50 p-3 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.04)] sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="font-mono text-xs text-af-on-surface">{t.name}</p>
                        {t.description && (
                          <p className="mt-0.5 text-[11px] leading-snug text-af-muted-dim">
                            {t.description}
                          </p>
                        )}
                        <p className="mt-1 text-[10px] uppercase text-af-muted-dim">
                          {t.skill_type}
                        </p>
                      </div>
                      <button
                        type="button"
                        disabled={have || installing === t.name}
                        onClick={() => void installTemplate(t.name)}
                        className="shrink-0 rounded-lg border border-af-border px-3 py-1.5 text-[11px] font-bold text-af-on-surface transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {have ? "Déjà installé" : installing === t.name ? "…" : "Installer"}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </ToolShell>
  );
}
