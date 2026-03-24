"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import React, { useCallback, useEffect, useRef, useState } from "react";
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
  total_steps: number | null;
  elapsed_seconds: number | null;
  eta_seconds: number | null;
  speed_spit: number | null;
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

function MetricCards({
  currentLoss,
  currentStep,
  totalSteps,
  history,
}: {
  currentLoss: number | null;
  currentStep: number;
  totalSteps: number;
  history: MetricPoint[];
}): React.ReactElement {
  const lastPt = history.length > 0 ? history[history.length - 1] : null;
  const cards: { label: string; value: string; highlight: boolean }[] = [
    { label: "Loss", value: currentLoss != null ? fmt(currentLoss) : "\u2014", highlight: true },
    { label: "Step", value: currentStep > 0 ? `${currentStep}${totalSteps > 0 ? ` / ${totalSteps}` : ""}` : "\u2014", highlight: false },
    { label: "Epoch", value: lastPt ? fmt(lastPt.epoch, 3) : "\u2014", highlight: false },
    { label: "Learning Rate", value: lastPt?.lr != null ? lastPt.lr.toExponential(2) : "\u2014", highlight: false },
    { label: "Grad Norm", value: lastPt?.grad_norm != null ? fmt(lastPt.grad_norm) : "\u2014", highlight: false },
  ];
  return (
    <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-5">
      {cards.map((card) => (
        <div
          key={card.label}
          className="rounded-lg border border-af-border/40 bg-af-surface-container p-4"
        >
          <p className="mb-1 text-[10px] uppercase tracking-wider text-af-muted-dim">
            {card.label}
          </p>
          <p
            className={`font-mono text-lg font-bold ${card.highlight ? "text-af-tertiary" : "text-af-on-surface"}`}
          >
            {card.value}
          </p>
        </div>
      ))}
    </div>
  );
}

function EvaluateSection({ jobId, endpoint }: { jobId: string; endpoint: string | null }) {
  const [prompts, setPrompts] = useState("");
  const [results, setResults] = useState<{ prompt: string; response: string; elapsed_seconds: number }[]>([]);
  const [loading, setLoading] = useState(false);
  const [evalError, setEvalError] = useState<string | null>(null);

  async function runEval() {
    if (!prompts.trim()) return;
    setLoading(true);
    setEvalError(null);
    try {
      const promptList = prompts.split("\n").filter((p) => p.trim());
      const res = await api<{ results: { prompt: string; response: string; elapsed_seconds: number }[] }>(
        `/api/v1/finetune/${jobId}/evaluate`,
        {
          method: "POST",
          body: JSON.stringify({ prompts: promptList, max_tokens: 128, temperature: 0.1 }),
        },
      );
      setResults(res.results || []);
    } catch (e) {
      setEvalError(e instanceof Error ? e.message : "Evaluation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-af-border/40 bg-af-surface-container p-6">
      <h2 className="mb-4 flex items-center gap-2 text-sm font-bold text-af-on-surface">
        <span className="material-symbols-outlined text-af-tertiary">science</span>
        Evaluate Model
      </h2>
      {!endpoint ? (
        <p className="text-xs text-af-muted-dim">Deploy the model first to run evaluations.</p>
      ) : (
        <>
          <p className="mb-3 text-xs text-af-muted">
            Enter prompts (one per line) to test the fine-tuned model. Max 20 prompts.
          </p>
          <textarea
            rows={4}
            value={prompts}
            onChange={(e) => setPrompts(e.target.value)}
            className="af-input mb-3 w-full resize-y font-mono text-xs"
            placeholder={"User: What is machine learning?\nAssistant:"}
          />
          <button
            type="button"
            onClick={runEval}
            disabled={loading || !prompts.trim()}
            className="af-btn-primary mb-4 flex items-center gap-2 px-4 py-2 text-sm disabled:opacity-50"
          >
            {loading ? (
              <span className="material-symbols-outlined animate-spin text-sm">autorenew</span>
            ) : (
              <span className="material-symbols-outlined text-sm">play_arrow</span>
            )}
            {loading ? "Running..." : "Run evaluation"}
          </button>
          {evalError && <p className="mb-3 text-xs text-af-error">{evalError}</p>}
          {results.length > 0 && (
            <div className="space-y-3">
              {results.map((r, i) => (
                <div key={i} className="rounded-lg border border-af-border/30 bg-af-surface-low p-4">
                  <div className="mb-2">
                    <p className="mb-1 text-[10px] uppercase tracking-wider text-af-muted-dim">Prompt</p>
                    <p className="font-mono text-xs text-af-muted">{r.prompt}</p>
                  </div>
                  <div className="mb-2">
                    <p className="mb-1 text-[10px] uppercase tracking-wider text-af-muted-dim">Response</p>
                    <p className="font-mono text-xs text-af-on-surface">{r.response}</p>
                  </div>
                  <p className="text-[10px] text-af-muted-dim">{r.elapsed_seconds}s</p>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function buildPoint(data: Record<string, unknown>): MetricPoint {
  return {
    step: Number(data.step ?? 0),
    loss: Number(data.loss ?? 0),
    epoch: data.epoch != null ? Number(data.epoch) : null,
    lr: data.learning_rate != null ? Number(data.learning_rate) : null,
    grad_norm: data.grad_norm != null ? Number(data.grad_norm) : null,
    total_steps: data.total_steps != null ? Number(data.total_steps) : null,
    elapsed_seconds: data.elapsed_seconds != null ? Number(data.elapsed_seconds) : null,
    eta_seconds: data.eta_seconds != null ? Number(data.eta_seconds) : null,
    speed_spit: data.speed_spit != null ? Number(data.speed_spit) : null,
    ts: Date.now(),
  };
}

function pointToLog(p: MetricPoint): string {
  const parts = [`step ${p.step}`, `loss ${p.loss.toFixed(4)}`];
  if (p.epoch != null) parts.push(`epoch ${p.epoch.toFixed(2)}`);
  if (p.lr != null) parts.push(`lr ${p.lr.toExponential(2)}`);
  if (p.grad_norm != null) parts.push(`grad_norm ${p.grad_norm.toFixed(4)}`);
  if (p.speed_spit != null) parts.push(`${p.speed_spit.toFixed(2)}s/it`);
  if (p.total_steps != null) {
    const pct = ((p.step / p.total_steps) * 100).toFixed(1);
    parts.push(`${pct}%`);
  }
  return parts.join(" | ");
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
      // Seed history from DB-stored history array, or fallback to single point
      if (data.metrics && data.metrics.step !== undefined) {
        const dbHistory = Array.isArray(data.metrics.history) ? data.metrics.history as Record<string, unknown>[] : null;
        if (dbHistory && dbHistory.length > 0) {
          const points = dbHistory.map((h) => buildPoint(h));
          setHistory((prev) => (prev.length === 0 ? points : prev));
          setLogs((prev) => {
            if (prev.length === 0) {
              return points.map((p) => ({ ts: p.ts, text: pointToLog(p) }));
            }
            return prev;
          });
        } else {
          const point = buildPoint(data.metrics);
          setHistory((prev) => (prev.length === 0 ? [point] : prev));
          setLogs((prev) => {
            if (prev.length === 0) {
              return [{ ts: Date.now(), text: pointToLog(point) }];
            }
            return prev;
          });
        }
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

  /* ---------- HTTP polling fallback ---------- */
  // When SSE doesn't deliver data (e.g. backend restarted and poll task lost),
  // poll the API every 10s to pick up metrics from the DB.
  useEffect(() => {
    if (!job || job.status.toLowerCase() !== "running") return;

    const interval = setInterval(async () => {
      try {
        const fresh = await api<Job>(`/api/v1/finetune/${id}`);
        setJob(fresh);
        if (fresh.metrics && fresh.metrics.step !== undefined) {
          const point = buildPoint(fresh.metrics);
          setHistory((prev) => {
            if (prev.length > 0 && prev[prev.length - 1].step >= point.step) return prev;
            return [...prev, point];
          });
          setLogs((prev) => {
            if (prev.length > 0 && prev[prev.length - 1].text.startsWith(`step ${point.step} `)) return prev;
            return [...prev.slice(-199), { ts: Date.now(), text: pointToLog(point) }];
          });
        }
        // If status changed to terminal, stop polling
        if (["completed", "failed", "cancelled"].includes(fresh.status.toLowerCase())) {
          clearInterval(interval);
        }
      } catch {
        // ignore poll errors
      }
    }, 10_000);

    return () => clearInterval(interval);
  }, [job?.status, id]);

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
            const point = buildPoint(data);

            setHistory((prev) => {
              if (prev.length > 0 && prev[prev.length - 1].step === point.step) return prev;
              return [...prev, point];
            });

            setJob((prev) => (prev ? { ...prev, metrics: data, status: "running" } : prev));

            setLogs((prev) => [
              ...prev.slice(-199),
              { ts: Date.now(), text: pointToLog(point) },
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
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.status, id]);

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  /* ---------- derived state ---------- */
  const isRunning = job?.status.toLowerCase() === "running";
  const last = history.length > 0 ? history[history.length - 1] : null;
  const currentStep = last?.step ?? 0;
  const currentLoss = last?.loss ?? null;

  // total_steps from server (trainer knows the real total), fallback to hyperparams
  const totalSteps = last?.total_steps ?? Number(job?.hyperparams?.max_steps ?? 0);
  const totalEpochs = Number(job?.hyperparams?.epochs ?? 0);

  // Progress
  let progressPct = 0;
  let progressLabel = "";
  if (totalSteps > 0 && currentStep > 0) {
    progressPct = Math.min((currentStep / totalSteps) * 100, 100);
    progressLabel = `${currentStep} / ${totalSteps} steps`;
  } else if (totalEpochs > 0 && last) {
    const curEpoch = last.epoch ?? 0;
    progressPct = Math.min((curEpoch / totalEpochs) * 100, 100);
    progressLabel = `epoch ${fmt(curEpoch, 2)} / ${totalEpochs}`;
  }

  // Elapsed & ETA — prefer server-side values (computed inside Modal GPU)
  let elapsedStr = "\u2014";
  let etaStr = "\u2014";
  let speedStr = "\u2014";
  if (last) {
    if (last.elapsed_seconds != null && last.elapsed_seconds > 0) {
      elapsedStr = fmtDuration(last.elapsed_seconds * 1000);
    }
    if (last.eta_seconds != null && last.eta_seconds > 0) {
      etaStr = fmtDuration(last.eta_seconds * 1000);
    }
    if (last.speed_spit != null && last.speed_spit > 0) {
      speedStr = `${last.speed_spit.toFixed(2)}s/it`;
    }
  }
  // Client-side fallback for ETA if server didn't provide it
  if (etaStr === "\u2014" && isRunning && history.length >= 2 && totalSteps > 0) {
    const first = history[0];
    const elapsed = last!.ts - first.ts;
    const stepsCompleted = last!.step - first.step;
    if (stepsCompleted > 0 && elapsed > 0) {
      const msPerStep = elapsed / stepsCompleted;
      const remaining = totalSteps - last!.step;
      if (remaining > 0) etaStr = fmtDuration(msPerStep * remaining);
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
              <span>{progressLabel} ({progressPct.toFixed(1)}%)</span>
              <div className="flex items-center gap-4">
                {elapsedStr !== "\u2014" && (
                  <span>
                    Elapsed: <strong className="text-af-on-surface">{elapsedStr}</strong>
                  </span>
                )}
                {speedStr !== "\u2014" && (
                  <span>
                    Speed: <strong className="text-af-on-surface">{speedStr}</strong>
                  </span>
                )}
                <span>
                  ETA: <strong className="text-af-on-surface">{etaStr}</strong>
                </span>
              </div>
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
      <MetricCards
        currentLoss={currentLoss}
        currentStep={currentStep}
        totalSteps={totalSteps}
        history={history}
      />

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

      {/* Sample inferences at checkpoints */}
      {Array.isArray(job.metrics?.samples) && (job.metrics.samples as { step: number; prompt: string; response: string }[]).length > 0 && (
        <div className="mt-8 rounded-xl border border-af-border/40 bg-af-surface-container p-6">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-bold text-af-on-surface">
            <span className="material-symbols-outlined text-af-tertiary">smart_toy</span>
            Sample Inferences (model evolution)
          </h2>
          <div className="space-y-4">
            {(job.metrics.samples as { step: number; prompt: string; response: string }[]).map((s, i) => (
              <div key={i} className="rounded-lg border border-af-border/30 bg-af-surface-low p-4">
                <div className="mb-2 flex items-center gap-2">
                  <span className="rounded bg-af-surface-high px-2 py-0.5 font-mono text-[10px] font-bold text-af-muted">
                    Step {s.step}
                  </span>
                </div>
                <div className="mb-2">
                  <p className="mb-1 text-[10px] uppercase tracking-wider text-af-muted-dim">Prompt</p>
                  <p className="font-mono text-xs text-af-muted">{s.prompt}</p>
                </div>
                <div>
                  <p className="mb-1 text-[10px] uppercase tracking-wider text-af-muted-dim">Response</p>
                  <p className="font-mono text-xs text-af-on-surface">{s.response}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Deploy + Evaluate — only for completed jobs */}
      {job.status.toLowerCase() === "completed" && (
        <div className="mt-8 space-y-6">
          {/* Deploy action */}
          {!job.inference_endpoint && (
            <div className="rounded-xl border border-af-primary/30 bg-af-primary/5 p-6">
              <h2 className="mb-2 flex items-center gap-2 text-sm font-bold text-af-on-surface">
                <span className="material-symbols-outlined text-af-primary">rocket_launch</span>
                Deploy Inference Endpoint
              </h2>
              <p className="mb-4 text-xs text-af-muted">
                Deploy this model to make it available as an LLM provider for your agents.
                Requires <code className="text-af-muted">modal deploy modal_functions/inference.py</code> first.
              </p>
              <button
                type="button"
                onClick={async () => {
                  try {
                    await api(`/api/v1/finetune/${id}/deploy`, { method: "POST" });
                    void loadJob();
                  } catch (e) {
                    if (e instanceof ApiError && e.status === 401) router.push("/login");
                  }
                }}
                className="af-btn-primary px-6 py-2 text-sm"
              >
                Deploy endpoint
              </button>
            </div>
          )}

          {/* Deployed status */}
          {job.inference_endpoint && (
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-6">
              <h2 className="mb-2 flex items-center gap-2 text-sm font-bold text-af-on-surface">
                <span className="material-symbols-outlined text-emerald-400">check_circle</span>
                Deployed
              </h2>
              <p className="font-mono text-xs text-af-muted">{job.inference_endpoint}</p>
              <p className="mt-2 text-xs text-af-muted-dim">
                Use this model in agent creation by selecting <strong className="text-af-on-surface">Fine-tuned model</strong> as the LLM provider.
              </p>
            </div>
          )}

          {/* Evaluate */}
          <EvaluateSection jobId={id as string} endpoint={job.inference_endpoint} />
        </div>
      )}

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
