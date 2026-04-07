"use client";
import { useEffect, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { api, ApiError } from "@/lib/api";
import { useRouter } from "next/navigation";

type DayStat = {
  day: string;
  total: number;
  completed: number;
  failed: number;
  avg_latency_ms: number;
  total_tokens: number;
};

type MetricsSummary = {
  total_executions: number;
  error_rate: number;
  avg_latency_ms: number;
  total_tokens: number;
  estimated_cost_usd: number;
};

type MetricsResponse = {
  daily_stats: DayStat[];
  summary: MetricsSummary;
};

function Sparkline({
  data,
  width = 200,
  height = 40,
  color = "#c3c0ff",
}: {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
}) {
  if (data.length < 2) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const pts = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((v - min) / range) * (height - 6) - 3;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinejoin="round"
      />
    </svg>
  );
}

const PERIODS = [
  { label: "7d", days: 7 },
  { label: "14d", days: 14 },
  { label: "30d", days: 30 },
];

export default function AnalyticsPage() {
  const router = useRouter();
  const [period, setPeriod] = useState(7);
  const [data, setData] = useState<MetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api<MetricsResponse>(`/api/v1/dashboard/metrics?days=${period}`)
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) router.push("/login");
        else {
          setError(e.message);
          setLoading(false);
        }
      });
  }, [period, router]);

  const stats = data?.summary;
  const daily = data?.daily_stats ?? [];

  return (
    <ToolShell active="analytics">
      <div className="mx-auto max-w-7xl pb-16">
        <header className="mb-10">
          <span className="af-kicker text-af-primary">[ ANALYTICS ]</span>
          <h1 className="mt-2 font-sans text-5xl font-bold tracking-tighter text-af-on-surface">
            Execution{" "}
            <span className="af-serif-italic text-af-primary">metrics</span>
          </h1>
        </header>

        {/* Period selector */}
        <div className="mb-8 flex gap-2">
          {PERIODS.map((p) => (
            <button
              key={p.days}
              type="button"
              onClick={() => setPeriod(p.days)}
              className={`rounded-lg border px-4 py-1.5 text-sm font-bold transition-colors ${
                period === p.days
                  ? "border-af-primary bg-af-primary/10 text-af-primary"
                  : "border-af-border text-af-muted hover:border-af-primary/40 hover:text-af-on-surface"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {loading && <p className="text-af-muted">Loading metrics...</p>}
        {error && <p className="text-af-error">{error}</p>}

        {stats && (
          <>
            {/* Summary cards */}
            <div className="mb-10 grid grid-cols-2 gap-4 md:grid-cols-5">
              {[
                {
                  label: "Executions",
                  value: stats.total_executions,
                  suffix: "",
                },
                {
                  label: "Error rate",
                  value: `${(stats.error_rate * 100).toFixed(1)}`,
                  suffix: "%",
                },
                {
                  label: "Avg latency",
                  value: stats.avg_latency_ms
                    ? `${(stats.avg_latency_ms / 1000).toFixed(1)}`
                    : "—",
                  suffix: stats.avg_latency_ms ? "s" : "",
                },
                {
                  label: "Total tokens",
                  value: stats.total_tokens.toLocaleString(),
                  suffix: "",
                },
                {
                  label: "Estimated cost",
                  value: `$${stats.estimated_cost_usd.toFixed(3)}`,
                  suffix: "",
                },
              ].map((c) => (
                <div key={c.label} className="af-card p-5">
                  <p className="af-kicker mb-3">{c.label}</p>
                  <p className="text-2xl font-bold text-af-on-surface">
                    {c.value}
                    <span className="text-lg text-af-muted">{c.suffix}</span>
                  </p>
                </div>
              ))}
            </div>

            {/* Daily executions bar chart */}
            <div className="af-card p-6">
              <p className="af-kicker mb-6">
                Daily executions — last {period} days
              </p>
              {daily.length === 0 ? (
                <p className="text-sm text-af-muted">
                  No execution data for this period.
                </p>
              ) : (
                <>
                  <div className="flex h-32 items-end gap-1.5">
                    {daily.map((d) => {
                      const maxTotal =
                        Math.max(...daily.map((x) => x.total)) || 1;
                      const pct = (d.total / maxTotal) * 100;
                      const failPct = d.total > 0 ? (d.failed / d.total) * 100 : 0;
                      return (
                        <div
                          key={d.day}
                          className="group relative flex flex-1 flex-col items-center gap-1"
                          title={`${d.day}: ${d.total} runs, ${d.failed} failed`}
                        >
                          {/* Tooltip */}
                          <div className="pointer-events-none absolute bottom-full mb-2 hidden rounded bg-af-surface-low px-2 py-1 text-[10px] text-af-on-surface shadow-lg group-hover:block whitespace-nowrap z-10">
                            <div className="font-bold">{d.day}</div>
                            <div>{d.total} runs</div>
                            {d.failed > 0 && (
                              <div className="text-af-error">{d.failed} failed</div>
                            )}
                            {d.avg_latency_ms > 0 && (
                              <div>{(d.avg_latency_ms / 1000).toFixed(1)}s avg</div>
                            )}
                          </div>
                          {/* Bar */}
                          <div
                            className="w-full rounded-t relative overflow-hidden"
                            style={{
                              height: `${Math.max(pct * 1.12, 4)}px`,
                              background: "var(--color-af-primary)",
                              opacity: 0.65 + (pct / 100) * 0.35,
                            }}
                          >
                            {failPct > 0 && (
                              <div
                                className="absolute bottom-0 left-0 w-full"
                                style={{
                                  height: `${failPct}%`,
                                  background: "var(--color-af-error, #f87171)",
                                  opacity: 0.8,
                                }}
                              />
                            )}
                          </div>
                          <span className="text-[9px] text-af-muted">
                            {d.day.slice(5)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  {/* Legend */}
                  <div className="mt-4 flex items-center gap-4 text-xs text-af-muted">
                    <span className="flex items-center gap-1.5">
                      <span className="inline-block h-2.5 w-2.5 rounded-sm bg-af-primary opacity-80" />
                      Completed
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span
                        className="inline-block h-2.5 w-2.5 rounded-sm opacity-80"
                        style={{ background: "var(--color-af-error, #f87171)" }}
                      />
                      Failed
                    </span>
                  </div>
                </>
              )}
            </div>

            {/* Latency sparkline (shown only if we have data) */}
            {daily.some((d) => d.avg_latency_ms > 0) && (
              <div className="af-card mt-4 p-6">
                <p className="af-kicker mb-4">Avg latency trend (ms)</p>
                <div className="flex items-center gap-6">
                  <Sparkline
                    data={daily.map((d) => d.avg_latency_ms)}
                    width={320}
                    height={56}
                    color="#c3c0ff"
                  />
                  <div className="text-sm text-af-muted">
                    <p>
                      Min:{" "}
                      <span className="font-bold text-af-on-surface">
                        {Math.min(...daily.map((d) => d.avg_latency_ms).filter(Boolean))}ms
                      </span>
                    </p>
                    <p>
                      Max:{" "}
                      <span className="font-bold text-af-on-surface">
                        {Math.max(...daily.map((d) => d.avg_latency_ms))}ms
                      </span>
                    </p>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </ToolShell>
  );
}
