"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";
import { consumeFinetuneSse } from "@/lib/sse";

/* ---------- types ---------- */

type Job = {
  id: string;
  base_model: string;
  dataset_path: string;
  status: string;
  metrics: Record<string, unknown> | null;
  hyperparams: Record<string, unknown>;
  inference_endpoint: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

type MetricPoint = {
  step: number;
  loss: number;
  epoch: number | null;
  lr: number | null;
  grad_norm: number | null;
  ts: number; // unix ms — for ETA
};

type LogEntry = { ts: number; text: string };

/* ---------- helpers ---------- */

function statusBadge(status: string) {
  const s = status.toLowerCase();
  if (s === "running")
    return "border-af-tertiary/30 bg-af-tertiary/10 text-af-tertiary";
  if (s === "completed")
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-400";
  if (s === "failed" || s === "cancelled")
    return "border-af-error/30 bg-af-error/10 text-af-error";
  return "border-af-secondary/20 bg-af-secondary/10 text-af-secondary";
}

function fmt(v: unknown, decimals = 4): string {
  if (v === null || v === undefined) return "\u2014";
  if (typeof v === "number") return v.toFixed(decimals);
  return String(v);
}

function fmtDuration(ms: number): string {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${sec}s`;
  return `${sec}s`;
}

/* ---------- custom tooltip ---------- */

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { value: number; name: string }[];
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-af-border bg-af-surface-container px-3 py-2 text-xs shadow-xl">
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="text-af-muted">{p.name}:</span>
          <span className="font-bold text-af-on-surface">
            {p.value.toFixed(4)}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ---------- main page ---------- */

export default function FinetuneDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<MetricPoint[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const sseCtrl = useRef<AbortController | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  /* ---------- load job ---------- */
  const loadJob = useCallback(async () => {
    try {
      const data = await api<Job>(`/api/v1/finetune/${id}`);
      setJob(data);
      // Seed history from last known metrics if we have none
      if (data.metrics && data.metrics.step !== undefined) {
        setHistory((prev) => {
          if (prev.length === 0) {
            return [
              {
                step: Number(data.metrics!.step),
                loss: Number(data.metrics!.loss ?? 0),
                epoch: data.metrics!.epoch != null ? Number(data.metrics!.epoch) : null,
                lr: data.metrics!.learning_rate != null ? Number(data.metrics!.learning_rate) : null,
                grad_norm: data.metrics!.grad_norm != null ? Number(data.metrics!.grad_norm) : null,
                ts: Date.now(),
              },
            ];
          }
          return prev;
        });
      }
      return data;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Failed to load job");
      return null;
    }
  }, [id, router]);

  useEffect(() => {
    void loadJob();
  }, [loadJob]);

  /* ---------- SSE streaming ---------- */
  useEffect(() => {
    if (!job || job.status.toLowerCase() !== "running") return;
    if (sseCtrl.current) return; // already streaming

    const ctrl = new AbortController();
    sseCtrl.current = ctrl;

    consumeFinetuneSse(
      id,
      (eventName, dataJson) => {
        if (eventName === "connected") {
          setConnected(true);
          return;
        }
        if (eventName === "ping") return;

        try {
          const payload = JSON.parse(dataJson) as Record<string, unknown>;

          if (eventName === "metrics") {
            const data = (payload.data ?? payload) as Record<string, unknown>;
            const step = Number(data.step ?? 0);
            const loss = Number(data.loss ?? 0);
            const epoch = data.epoch != null ? Number(data.epoch) : null;
            const lr = data.learning_rate != null ? Number(data.learning_rate) : null;
            const grad_norm = data.grad_norm != null ? Number(data.grad_norm) : null;

            const point: MetricPoint = { step, loss, epoch, lr, grad_norm, ts: Date.now() };

            setHistory((prev) => {
              // Dedupe by step
              if (prev.length > 0 && prev[prev.length - 1].step === step) return prev;
              return [...prev, point];
            });

            // Update job metrics inline
            setJob((prev) => (prev ? { ...prev, metrics: data, status: "running" } : prev));

            // Add to log
            setLogs((prev) => [
              ...prev.slice(-199),
              {
                ts: Date.now(),
                text: `step ${step} | loss ${loss.toFixed(4)}${epoch != null ? ` | epoch ${epoch.toFixed(4)}` : ""}${lr != null ? ` | lr ${lr.toExponential(2)}` : ""}${grad_norm != null ? ` | grad_norm ${grad_norm.toFixed(4)}` : ""}`,
              },
            ]);
          } else if (["completed", "failed", "cancelled"].includes(eventName)) {
            setLogs((prev) => [
              ...prev,
              { ts: Date.now(), text: `Training ${eventName}.` },
            ]);
            void loadJob();
            sseCtrl.current = null;
          }
        } catch {
          // ignore
        }
      },
      ctrl.signal,
    ).catch(() => {
      setConnected(false);
      sseCtrl.current = null;
    });

    return () => {
      ctrl.abort();
      sseCtrl.current = null;
      setConnected(false);
    };
  }, [job?.status, id, loadJob, job]);

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  /* ---------- derived state ---------- */
  const isRunning = job?.status.toLowerCase() === "running";
  const maxSteps = Number(job?.hyperparams?.max_steps ?? 0);
  const totalEpochs = Number(job?.hyperparams?.epochs ?? 0);
  const currentStep = history.length > 0 ? history[history.length - 1].step : 0;
  const currentLoss = history.length > 0 ? history[history.length - 1].loss : null;

  // Progress: prefer step-based if max_steps known
  let progressPct = 0;
  let progressLabel = "";
  if (maxSteps > 0 && currentStep > 0) {
    progressPct = Math.min((currentStep / maxSteps) * 100, 100);
    progressLabel = `${currentStep} / ${maxSteps} steps`;
  } else if (totalEpochs > 0 && history.length > 0) {
    const curEpoch = history[history.length - 1].epoch ?? 0;
    progressPct = Math.min((curEpoch / totalEpochs) * 100, 100);
    progressLabel = `epoch ${fmt(curEpoch, 2)} / ${totalEpochs}`;
  }

  // ETA estimation based on step timing
  let etaStr = "\u2014";
  if (isRunning && history.length >= 2 && (maxSteps > 0 || totalEpochs > 0)) {
    const first = history[0];
    const last = history[history.length - 1];
    const elapsed = last.ts - first.ts;
    const stepsCompleted = last.step - first.step;
    if (stepsCompleted > 0 && elapsed > 0) {
      const msPerStep = elapsed / stepsCompleted;
      const stepsRemaining = maxSteps > 0 ? maxSteps - last.step : 0;
      if (stepsRemaining > 0) {
        etaStr = fmtDuration(msPerStep * stepsRemaining);
      }
    }
  }

  if (!job) {
    return (
      <ToolShell active="finetune">
        <div className="flex h-64 items-center justify-center">
          {error ? (
            <p className="text-af-error">{error}</p>
          ) : (
            <span className="material-symbols-outlined animate-spin text-3xl text-af-muted">
              autorenew
            </span>
          )}
        </div>
      </ToolShell>
    );
  }

  return (
    <ToolShell active="finetune">
      {/* Back link */}
      <Link
        href="/finetune"
        className="mb-6 inline-flex items-center gap-1 text-sm text-af-muted hover:text-af-primary"
      >
        <span className="material-symbols-outlined text-sm">arrow_back</span>
        Fine-tune
      </Link>

      {/* Header */}
      <header className="mb-8">
        <div className="mb-2 flex items-center gap-3">
          <span className="af-kicker">[ JOB ]</span>
          {connected && isRunning && (
            <span className="flex items-center gap-1 text-[10px] text-af-tertiary">
              <span className="material-symbols-outlined animate-spin text-sm">
                autorenew
              </span>
              Live
            </span>
          )}
        </div>
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="font-sans text-3xl tracking-tight text-af-on-surface md:text-4xl">
              {job.base_model}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <span className="rounded bg-af-surface-high px-2 py-0.5 font-mono text-[10px] text-af-muted-dim">
                {job.id.slice(0, 8)}
              </span>
              <span
                className={`rounded-full border px-3 py-1 text-[10px] font-bold ${statusBadge(job.status)}`}
              >
                {job.status}
              </span>
              <span className="font-mono text-xs text-af-muted">
                {job.dataset_path}
              </span>
            </div>
          </div>
          {isRunning && (
            <button
              type="button"
              onClick={async () => {
                try {
                  await api(`/api/v1/finetune/${id}/cancel`, {
                    method: "DELETE",
                  });
                  void loadJob();
                } catch (e) {
                  if (e instanceof ApiError && e.status === 401)
                    router.push("/login");
                }
              }}
              className="rounded-lg border border-af-error/40 px-4 py-2 text-xs font-bold text-af-error hover:bg-af-error/10"
            >
              Stop training
            </button>
          )}
        </div>
      </header>

      {/* Progress bar */}
      {(isRunning || job.status.toLowerCase() === "completed") &&
        progressPct > 0 && (
          <div className="mb-8">
            <div className="mb-2 flex items-center justify-between text-xs text-af-muted">
              <span>{progressLabel}</span>
              <span>
                ETA: <strong className="text-af-on-surface">{etaStr}</strong>
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-af-surface-high">
              <div
                className="h-full rounded-full bg-gradient-to-r from-af-indigo to-af-tertiary transition-all duration-500"
                style={{
                  width: `${job.status.toLowerCase() === "completed" ? 100 : progressPct}%`,
                }}
              />
            </div>
          </div>
        )}

      {/* Metrics cards */}
      <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-5">
        {[
          {
            label: "Loss",
            value: currentLoss != null ? fmt(currentLoss) : "\u2014",
            highlight: true,
          },
          {
            label: "Step",
            value:
              currentStep > 0
                ? `${currentStep}${maxSteps > 0 ? ` / ${maxSteps}` : ""}`
                : "\u2014",
          },
          {
            label: "Epoch",
            value: history.length > 0 ? fmt(history[history.length - 1].epoch, 3) : "\u2014",
          },
          {
            label: "Learning Rate",
            value:
              history.length > 0 && history[history.length - 1].lr != null
                ? history[history.length - 1].lr!.toExponential(2)
                : "\u2014",
          },
          {
            label: "Grad Norm",
            value:
              history.length > 0 && history[history.length - 1].grad_norm != null
                ? fmt(history[history.length - 1].grad_norm)
                : "\u2014",
          },
        ].map(({ label, value, highlight }) => (
          <div
            key={label}
            className="rounded-lg border border-af-border/40 bg-af-surface-container p-4"
          >
            <p className="mb-1 text-[10px] uppercase tracking-wider text-af-muted-dim">
              {label}
            </p>
            <p
              className={`font-mono text-lg font-bold ${highlight ? "text-af-tertiary" : "text-af-on-surface"}`}
            >
              {value}
            </p>
          </div>
        ))}
      </div>

      {/* Loss chart */}
      {history.length > 1 && (
        <div className="mb-8 rounded-xl border border-af-border/40 bg-af-surface-container p-6">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-bold text-af-on-surface">
            <span className="material-symbols-outlined text-af-primary">
              show_chart
            </span>
            Training Loss
          </h2>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart
              data={history}
              margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
            >
              <defs>
                <linearGradient id="lossGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#4f46e5" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#4f46e5" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#1e1e30"
                vertical={false}
              />
              <XAxis
                dataKey="step"
                tick={{ fill: "#555566", fontSize: 10 }}
                axisLine={{ stroke: "#1e1e30" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#555566", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                width={50}
                domain={["auto", "auto"]}
              />
              <Tooltip content={<ChartTooltip />} />
              <Area
                type="monotone"
                dataKey="loss"
                stroke="#4f46e5"
                strokeWidth={2}
                fill="url(#lossGrad)"
                dot={false}
                animationDuration={300}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Grad norm chart (if available) */}
      {history.length > 1 && history.some((p) => p.grad_norm != null) && (
        <div className="mb-8 rounded-xl border border-af-border/40 bg-af-surface-container p-6">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-bold text-af-on-surface">
            <span className="material-symbols-outlined text-af-tertiary">
              trending_down
            </span>
            Gradient Norm
          </h2>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart
              data={history.filter((p) => p.grad_norm != null)}
              margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
            >
              <defs>
                <linearGradient id="gradGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3cddc7" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#3cddc7" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#1e1e30"
                vertical={false}
              />
              <XAxis
                dataKey="step"
                tick={{ fill: "#555566", fontSize: 10 }}
                axisLine={{ stroke: "#1e1e30" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#555566", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                width={50}
              />
              <Tooltip content={<ChartTooltip />} />
              <Area
                type="monotone"
                dataKey="grad_norm"
                stroke="#3cddc7"
                strokeWidth={2}
                fill="url(#gradGrad)"
                dot={false}
                animationDuration={300}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Live log stream */}
      <div className="rounded-xl border border-af-border/40 bg-af-surface-container">
        <div className="flex items-center justify-between border-b border-af-border/40 px-6 py-3">
          <h2 className="flex items-center gap-2 text-sm font-bold text-af-on-surface">
            <span className="material-symbols-outlined text-af-muted">
              terminal
            </span>
            Training Logs
          </h2>
          {isRunning && connected && (
            <span className="flex items-center gap-1.5 text-[10px] text-af-tertiary">
              <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-af-tertiary" />
              Streaming
            </span>
          )}
        </div>
        <div className="h-64 overflow-y-auto px-6 py-4 font-mono text-xs leading-6 text-af-muted">
          {logs.length === 0 && (
            <p className="text-af-muted-dim">
              {isRunning
                ? "Waiting for training metrics..."
                : "No logs recorded for this job."}
            </p>
          )}
          {logs.map((l, i) => (
            <div key={i} className="flex gap-3">
              <span className="shrink-0 text-af-muted-dim">
                {new Date(l.ts).toLocaleTimeString()}
              </span>
              <span className="text-af-on-surface">{l.text}</span>
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      </div>

      {/* Hyperparams summary */}
      <div className="mt-8 rounded-xl border border-af-border/40 bg-af-surface-container p-6">
        <h2 className="mb-4 flex items-center gap-2 text-sm font-bold text-af-on-surface">
          <span className="material-symbols-outlined text-af-muted">tune</span>
          Hyperparameters
        </h2>
        <div className="grid grid-cols-2 gap-4 font-mono text-xs md:grid-cols-4">
          {Object.entries(job.hyperparams).map(([k, v]) => (
            <div key={k}>
              <p className="mb-1 text-af-muted-dim">{k}</p>
              <p className="text-af-on-surface">{String(v)}</p>
            </div>
          ))}
        </div>
      </div>
    </ToolShell>
  );
}
