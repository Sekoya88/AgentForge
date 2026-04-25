"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { CSSProperties } from "react";
import { useEffect, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { useChatContext } from "@/contexts/ChatContext";
import { useScrollReveal } from "@/hooks/useScrollReveal";
import { useCountUp } from "@/hooks/useCountUp";
import { ApiError, api } from "@/lib/api";
import { ProductTour } from "@/components/onboarding/ProductTour";
import { OnboardingChecklist } from "@/components/ui/OnboardingChecklist";
import {
  isProductTourV1Done,
  setProductTourV1Done,
  stepIdsCompletedFromStats,
} from "@/lib/onboarding";

type DashboardStats = {
  agents: number;
  executions: number;
  avg_duration_ms: number | null;
  campaigns: number;
  avg_security_score: number | null;
  skills: number;
  knowledge_sources: number;
  recent_executions: {
    id: string;
    agent_id: string;
    status: string;
    duration_ms: number | null;
    started_at: string | null;
  }[];
};

// CSS hex color per stat type for glow
const STAT_GLOW: Record<string, string> = {
  smart_toy: "#c3c0ff",
  play_circle: "#3cddc7",
  speed: "#f59e0b",
  timer: "#f59e0b",
  verified_user: "#34d399",
  shield: "#34d399",
  psychology: "#a78bfa",
  menu_book: "#38bdf8",
  rocket_launch: "#fb923c",
};

function StatCard({
  label,
  value,
  sub,
  icon,
  color = "text-af-primary",
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: string;
  color?: string;
}) {
  const [ref, visible] = useScrollReveal<HTMLDivElement>({ threshold: 0.2 });
  const numericValue = typeof value === "number" ? value : parseFloat(String(value));
  const isNumeric = !isNaN(numericValue);
  const animated = useCountUp(isNumeric ? numericValue : 0, visible, 900);
  const glowColor = STAT_GLOW[icon] ?? "#c3c0ff";

  return (
    <div
      ref={ref}
      className={`af-stat-card group flex cursor-default flex-col justify-between rounded-xl border border-af-border/55 bg-af-surface-container/95 p-5 shadow-sm backdrop-blur-md transition-[opacity,transform,box-shadow,border-color] duration-300 ease-out hover:border-af-primary/30 hover:shadow-md ${
        visible ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-3 opacity-0"
      }`}
      style={
        {
          transitionDuration: "0.45s, 0.45s, 0.2s, 0.2s",
          ["--af-stat-accent" as string]: glowColor,
        } as CSSProperties
      }
    >
      <div className="mb-3 flex items-center gap-2">
        <span
          className="material-symbols-outlined text-lg text-[color:var(--af-stat-accent)] transition-all group-hover:drop-shadow-[0_0_8px_var(--af-stat-accent)]"
          style={{ filter: visible ? `drop-shadow(0 0 6px color-mix(in srgb, var(--af-stat-accent) 50%, transparent))` : "none" }}
        >
          {icon}
        </span>
        <span className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">{label}</span>
      </div>
      <span
        className={`text-3xl font-bold tabular-nums ${color}`}
        style={{ textShadow: visible ? `0 0 20px ${glowColor}40` : "none" }}
      >
        {isNumeric ? animated : value}
      </span>
      {sub && <span className="mt-1 text-xs text-af-muted">{sub}</span>}
    </div>
  );
}

function statusColor(s: string) {
  if (/complete|success/i.test(s)) return "text-emerald-400";
  if (/run|progress/i.test(s)) return "text-amber-400";
  if (/fail|error/i.test(s)) return "text-red-400";
  return "text-af-muted";
}

export default function DashboardPage() {
  const router = useRouter();
  const { openChat } = useChatContext();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tourRun, setTourRun] = useState(false);
  const [showTourCta, setShowTourCta] = useState(false);

  useEffect(() => {
    setShowTourCta(!isProductTourV1Done());
  }, []);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const d = await api<DashboardStats>("/api/v1/dashboard");
        if (!c) setStats(d);
      } catch (e) {
        if (!c) {
          if (e instanceof ApiError && e.status === 401) {
            router.push("/login");
            return;
          }
          setError(e instanceof Error ? e.message : "Failed to load");
        }
      }
    })();
    return () => { c = true; };
  }, [router]);

  const derivedComplete =
    stats != null
      ? stepIdsCompletedFromStats({
          agents: stats.agents,
          knowledge_sources: stats.knowledge_sources,
          campaigns: stats.campaigns,
        })
      : undefined;

  function finishTour() {
    setProductTourV1Done();
    setTourRun(false);
    setShowTourCta(false);
  }

  return (
    <ToolShell active="dashboard">
      <ProductTour run={tourRun} onComplete={finishTour} />
      <div className="mx-auto max-w-6xl">
        <div className="mb-2 flex items-baseline gap-2">
          <span className="af-kicker text-af-primary">[ DASHBOARD ]</span>
        </div>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h1
            data-tour="dashboard-title"
            className="font-sans text-4xl font-bold tracking-tighter text-af-on-surface md:text-5xl"
          >
            Mission <span className="af-serif-italic text-af-primary">control</span>
          </h1>
          {showTourCta && (
            <button
              type="button"
              onClick={() => setTourRun(true)}
              className="rounded-lg border border-af-primary/50 bg-af-primary/10 px-4 py-2 text-xs font-bold uppercase tracking-wide text-af-primary transition-colors hover:bg-af-primary/20"
            >
              Start tour
            </button>
          )}
        </div>

        <OnboardingChecklist derivedComplete={derivedComplete} />

        {error && (
          <p className="mb-6 rounded-lg border border-af-error/30 bg-af-error/10 px-4 py-3 text-sm text-af-error">
            {error}
          </p>
        )}

        {!stats && !error && (
          <div className="space-y-4">
            <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="animate-pulse rounded-xl border border-af-border/50 bg-af-surface-container p-5">
                  <div className="mb-3 h-3 w-16 rounded bg-af-surface-high" />
                  <div className="h-8 w-12 rounded bg-af-surface-high" />
                </div>
              ))}
            </div>
            <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="animate-pulse rounded-xl border border-af-border/50 bg-af-surface-container p-5">
                  <div className="mb-3 h-3 w-16 rounded bg-af-surface-high" />
                  <div className="h-8 w-12 rounded bg-af-surface-high" />
                </div>
              ))}
            </div>
          </div>
        )}

        {stats && (
          <>
            <section className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
              <StatCard label="Agents" value={stats.agents} icon="smart_toy" color="text-af-primary" />
              <StatCard label="Executions" value={stats.executions} icon="play_circle" color="text-af-tertiary" />
              <StatCard
                label="Avg latency"
                value={stats.avg_duration_ms != null ? `${Math.round(stats.avg_duration_ms)}ms` : "—"}
                icon="timer"
                color="text-amber-500"
              />
              <StatCard
                label="Security"
                value={stats.avg_security_score != null ? stats.avg_security_score.toFixed(1) : "—"}
                sub={`${stats.campaigns} campaign${stats.campaigns !== 1 ? "s" : ""}`}
                icon="shield"
                color="text-af-secondary"
              />
            </section>

            <section className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-3">
              <StatCard label="Skills" value={stats.skills} icon="psychology" color="text-blue-400" />
              <StatCard label="Knowledge" value={stats.knowledge_sources} sub="indexed sources" icon="menu_book" color="text-purple-400" />
              <StatCard label="Campaigns" value={stats.campaigns} icon="rocket_launch" color="text-rose-400" />
            </section>

            {/* Quick actions */}
            <section className="mb-8 flex flex-wrap gap-3">
              <Link href="/agents/new" className="af-btn-primary flex items-center gap-2 px-5 py-2.5 text-sm">
                <span className="material-symbols-outlined text-sm">add</span>
                New agent
              </Link>
              <Link
                href="/forge"
                className="flex items-center gap-2 rounded-lg border border-af-primary/40 bg-af-primary/10 px-5 py-2.5 text-sm text-af-primary transition-colors hover:border-af-primary hover:bg-af-primary/20"
              >
                <span className="material-symbols-outlined text-sm">bolt</span>
                Open Forge
              </Link>
              <Link
                href="/skills/new"
                className="rounded-lg border border-af-border px-5 py-2.5 text-sm text-af-on-surface transition-colors hover:border-af-primary hover:text-af-primary"
              >
                New skill
              </Link>
              <Link
                href="/knowledge"
                className="rounded-lg border border-af-border px-5 py-2.5 text-sm text-af-on-surface transition-colors hover:border-af-primary hover:text-af-primary"
              >
                Ingest knowledge
              </Link>
              <Link
                href="/sandbox"
                className="rounded-lg border border-af-border px-5 py-2.5 text-sm text-af-on-surface transition-colors hover:border-af-primary hover:text-af-primary"
              >
                Sandbox
              </Link>
            </section>

            {/* Recent executions */}
            <section>
              <div className="mb-3 flex items-center justify-between">
                <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                  Recent executions
                </p>
                {stats.executions > 0 && (
                  <Link href="/executions" className="text-xs text-af-muted hover:text-af-primary">
                    View all {stats.executions} →
                  </Link>
                )}
              </div>
              {stats.recent_executions.length === 0 ? (
                <div className="rounded-xl border border-dashed border-af-border/40 bg-af-surface-container/20 p-8 text-center">
                  <span className="material-symbols-outlined mb-2 text-3xl text-af-muted">play_circle</span>
                  <p className="text-sm text-af-muted">No executions yet. Create an agent and run it.</p>
                </div>
              ) : (
                <div className="overflow-hidden rounded-xl border border-af-border/40 bg-af-surface-container/40">
                  <div className="divide-y divide-af-border/20">
                    {stats.recent_executions.map((ex) => (
                      <div
                        key={ex.id}
                        className="flex items-center justify-between gap-4 px-5 py-3 transition-colors hover:bg-af-on-surface/[0.04]"
                      >
                        <Link
                          href={`/agents/${ex.agent_id}`}
                          className="flex min-w-0 flex-1 items-center gap-3"
                        >
                          <span className="font-mono text-xs text-af-muted-dim">{ex.id.slice(0, 8)}</span>
                          <span className={`text-xs font-bold uppercase ${statusColor(ex.status)}`}>
                            {ex.status}
                          </span>
                        </Link>
                        <div className="flex shrink-0 items-center gap-3">
                          <button
                            type="button"
                            onClick={() => openChat(ex.agent_id)}
                            title="Ouvrir le chat pour cet agent"
                            className="flex h-8 w-8 items-center justify-center rounded-md border border-af-border/60 text-af-muted transition-colors hover:border-af-primary hover:text-af-primary"
                          >
                            <span className="material-symbols-outlined text-sm">chat</span>
                          </button>
                          <div className="flex items-center gap-4 text-right">
                            {ex.duration_ms != null && (
                              <span className="text-xs text-af-muted">{ex.duration_ms}ms</span>
                            )}
                            {ex.started_at && (
                              <span className="text-xs text-af-muted-dim">
                                {new Date(ex.started_at).toLocaleString()}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </ToolShell>
  );
}
