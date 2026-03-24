"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";
import { consumeFinetuneSse } from "@/lib/sse";

type Job = {
  id: string;
  base_model: string;
  dataset_path: string;
  status: string;
  metrics: Record<string, unknown> | null;
  inference_endpoint: string | null;
};

function jobStatusStyle(status: string) {
  const s = status.toLowerCase();
  if (s === "running") return "border-af-tertiary/20 bg-af-tertiary/10 text-af-tertiary";
  if (s === "completed") return "border-white/10 bg-white/5 text-af-muted";
  if (s === "failed" || s === "cancelled")
    return "border-af-error/30 bg-af-error/10 text-af-error";
  return "border-af-secondary/20 bg-af-secondary/10 text-af-secondary";
}

function formatMetric(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number" && !Number.isInteger(v)) return v.toFixed(4);
  return String(v);
}

export default function FinetunePage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [deployId, setDeployId] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  // Track active SSE abort controllers keyed by job_id
  const sseControllers = useRef<Map<string, AbortController>>(new Map());

  const loadJobs = useCallback(async () => {
    try {
      const data = await api<Job[]>("/api/v1/finetune");
      setJobs(data);
      setError(null);
      return data;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        router.push("/login");
        return null;
      }
      setError(e instanceof Error ? e.message : "Failed to load jobs");
      return null;
    }
  }, [router]);

  useEffect(() => {
    void loadJobs();
  }, [loadJobs]);

  // SSE: open a stream for each running job, close when terminal event received
  useEffect(() => {
    if (!jobs) return;

    const running = jobs.filter((j) => j.status.toLowerCase() === "running");
    setStreaming(running.length > 0);

    // Open SSE for newly running jobs not yet tracked
    for (const job of running) {
      if (sseControllers.current.has(job.id)) continue;
      const ctrl = new AbortController();
      sseControllers.current.set(job.id, ctrl);

      consumeFinetuneSse(
        job.id,
        (eventName, dataJson) => {
          if (eventName === "ping" || eventName === "connected") return;
          try {
            const payload = JSON.parse(dataJson) as Record<string, unknown>;
            if (eventName === "metrics") {
              setJobs((prev) =>
                prev
                  ? prev.map((j) =>
                      j.id === job.id
                        ? { ...j, metrics: payload.data as Record<string, unknown> }
                        : j,
                    )
                  : prev,
              );
            } else if (["completed", "failed", "cancelled"].includes(eventName)) {
              // Terminal event — reload full list to get accurate status
              void loadJobs();
              sseControllers.current.delete(job.id);
            }
          } catch {
            // ignore parse errors
          }
        },
        ctrl.signal,
      ).catch(() => {
        // SSE closed or errored — fall back to a single reload
        void loadJobs();
        sseControllers.current.delete(job.id);
      });
    }

    // Abort SSE for jobs no longer running
    for (const [id, ctrl] of sseControllers.current.entries()) {
      if (!running.some((j) => j.id === id)) {
        ctrl.abort();
        sseControllers.current.delete(id);
      }
    }
  }, [jobs, loadJobs]);

  // Cleanup all SSE on unmount
  useEffect(() => {
    return () => {
      for (const ctrl of sseControllers.current.values()) ctrl.abort();
    };
  }, []);

  async function cancelJob(id: string) {
    setActionBusy(true);
    try {
      await api(`/api/v1/finetune/${id}/cancel`, { method: "DELETE" });
      await loadJobs();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Cancel failed");
    } finally {
      setActionBusy(false);
    }
  }

  async function confirmDeploy() {
    if (!deployId) return;
    setActionBusy(true);
    try {
      await api<Job>(`/api/v1/finetune/${deployId}/deploy`, { method: "POST" });
      setDeployId(null);
      await loadJobs();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Deploy failed");
    } finally {
      setActionBusy(false);
    }
  }

  async function confirmDelete() {
    if (!deleteId) return;
    setActionBusy(true);
    try {
      await api(`/api/v1/finetune/${deleteId}`, { method: "DELETE" });
      setDeleteId(null);
      await loadJobs();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setActionBusy(false);
    }
  }

  const runningCount = jobs?.filter((j) => j.status.toLowerCase() === "running").length ?? 0;
  const completedCount = jobs?.filter((j) => j.status.toLowerCase() === "completed").length ?? 0;

  return (
    <ToolShell active="finetune">
      <header className="mb-12">
        <div className="mb-2 flex items-center gap-2">
          <span className="text-[10px] font-bold tracking-[0.3em] text-af-primary uppercase">[ FINE-TUNE ]</span>
          <div className="h-px w-12 bg-af-primary/30" />
          {streaming && (
            <span className="flex items-center gap-1 text-[10px] text-af-muted" title="Live metrics via SSE">
              <span className="material-symbols-outlined animate-spin text-sm text-af-tertiary">autorenew</span>
              Live
            </span>
          )}
        </div>
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div>
            <h1 className="font-sans text-4xl tracking-tighter text-af-on-surface md:text-6xl">
              Model <span className="af-serif-italic">refinement</span>
            </h1>
            <p className="mt-4 max-w-xl text-sm leading-relaxed text-af-muted">
              Monitor LoRA / QLoRA jobs. Metrics update while status is <strong className="text-af-on-surface">running</strong>
              .
            </p>
          </div>
          <Link
            href="/finetune/new"
            className="af-btn-primary inline-flex items-center gap-2 px-8 py-4 text-sm"
          >
            <span className="material-symbols-outlined">add_circle</span>
            New job
          </Link>
        </div>
      </header>

      <div className="mb-12 grid grid-cols-1 gap-6 md:grid-cols-3">
        {[
          ["Jobs", jobs?.length ?? "—"],
          ["Running", runningCount],
          ["Completed", completedCount],
        ].map(([k, v]) => (
          <div key={String(k)} className="rounded-lg border border-af-border/40 bg-af-surface-container p-6">
            <p className="mb-2 text-[10px] tracking-wider text-af-muted-dim uppercase">{k}</p>
            <div className="text-3xl font-bold text-af-on-surface">{v}</div>
          </div>
        ))}
      </div>

      {error && (
        <p className="mb-6 rounded-lg border border-af-error/30 bg-af-error/10 px-4 py-3 text-sm text-af-error">
          {error}
        </p>
      )}

      {jobs && jobs.length === 0 && (
        <div className="flex min-h-[300px] flex-col items-center justify-center rounded-xl border border-dashed border-af-border/60 bg-af-surface-container/20 p-12 text-center shadow-inner">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full border border-af-border/80 bg-af-surface-high text-af-muted">
            <span className="material-symbols-outlined text-3xl">tune</span>
          </div>
          <h3 className="mb-2 text-lg font-bold text-white">No fine-tuning jobs yet</h3>
          <p className="mb-6 max-w-sm text-sm text-af-muted">
            Create a job to adapt a base model. Enable Modal in the API for real GPU training.
          </p>
          <Link href="/finetune/new" className="af-btn-primary px-6 py-2.5 text-sm">
            Create your first job
          </Link>
        </div>
      )}

      {jobs && jobs.length > 0 && (
        <div className="space-y-4">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-bold">
            <span className="material-symbols-outlined text-af-primary">analytics</span>
            Job history
          </h2>
          {jobs.map((j) => {
            const st = j.status.toLowerCase();
            const m = j.metrics;
            return (
              <Link
                key={j.id}
                href={`/finetune/${j.id}`}
                className="block rounded-xl border border-transparent bg-af-surface-container p-1 transition-all hover:border-af-indigo/20"
              >
                <div className="flex flex-col gap-4 rounded-lg bg-af-surface-low p-6 md:flex-row md:items-start md:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="mb-2 flex flex-wrap items-center gap-3">
                      <span className="rounded bg-af-surface-high px-2 py-0.5 font-mono text-[10px] font-bold text-af-muted-dim">
                        {j.id.slice(0, 8)}
                      </span>
                      <h3 className="font-bold text-af-on-surface">{j.base_model}</h3>
                      <span
                        className={`rounded-full border px-3 py-1 text-[10px] font-bold ${jobStatusStyle(j.status)}`}
                      >
                        {j.status}
                      </span>
                    </div>
                    <p className="mb-2 truncate font-mono text-xs text-af-muted">{j.dataset_path}</p>
                    {m && (m.loss !== undefined || m.epoch !== undefined || m.step !== undefined) && (
                      <p className="font-mono text-xs text-af-muted">
                        loss {formatMetric(m.loss)} · epoch {formatMetric(m.epoch)} · step {formatMetric(m.step)}
                      </p>
                    )}
                    {j.inference_endpoint && (
                      <p className="mt-2 truncate font-mono text-xs text-af-muted">{j.inference_endpoint}</p>
                    )}
                  </div>
                  <div
                    className="flex flex-wrap items-center gap-2 md:justify-end"
                    onClick={(e) => e.preventDefault()}
                  >
                    {st === "running" && (
                      <button
                        type="button"
                        disabled={actionBusy}
                        onClick={(e) => {
                          e.preventDefault();
                          void cancelJob(j.id);
                        }}
                        className="rounded-lg border border-af-error/40 px-3 py-2 text-xs font-bold text-af-error hover:bg-af-error/10 disabled:opacity-50"
                      >
                        Stop training
                      </button>
                    )}
                    {st === "completed" && !j.inference_endpoint && (
                      <button
                        type="button"
                        disabled={actionBusy}
                        onClick={(e) => {
                          e.preventDefault();
                          setDeployId(j.id);
                        }}
                        className="rounded-lg border border-af-primary/40 px-3 py-2 text-xs font-bold text-af-primary hover:bg-af-primary/10 disabled:opacity-50"
                      >
                        Deploy endpoint
                      </button>
                    )}
                    <button
                      type="button"
                      disabled={actionBusy}
                      onClick={(e) => {
                        e.preventDefault();
                        setDeleteId(j.id);
                      }}
                      className="inline-flex items-center justify-center rounded-lg border border-af-border/60 p-2 text-af-muted hover:border-af-error/50 hover:text-af-error disabled:opacity-50"
                      aria-label="Delete job"
                    >
                      <span className="material-symbols-outlined text-lg">delete</span>
                    </button>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {deployId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <div className="af-card max-w-md w-full space-y-4 p-6 shadow-xl">
            <h3 className="text-lg font-bold text-white">Deploy inference endpoint?</h3>
            <p className="text-sm text-af-muted">
              Registers a placeholder inference URL for this job. Replace with a real Modal web endpoint when your
              inference app is deployed.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                disabled={actionBusy}
                onClick={() => setDeployId(null)}
                className="rounded-lg border border-af-border/60 px-4 py-2 text-sm text-af-muted hover:bg-af-surface-high"
              >
                Back
              </button>
              <button
                type="button"
                disabled={actionBusy}
                onClick={() => void confirmDeploy()}
                className="af-btn-primary px-4 py-2 text-sm disabled:opacity-50"
              >
                {actionBusy ? "…" : "Deploy"}
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <div className="af-card max-w-md w-full space-y-4 p-6 shadow-xl">
            <h3 className="text-lg font-bold text-white">Delete job permanently?</h3>
            <p className="text-sm text-af-muted">This removes the job record from the database. This cannot be undone.</p>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                disabled={actionBusy}
                onClick={() => setDeleteId(null)}
                className="rounded-lg border border-af-border/60 px-4 py-2 text-sm text-af-muted hover:bg-af-surface-high"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={actionBusy}
                onClick={() => void confirmDelete()}
                className="rounded-lg border border-af-error/50 bg-af-error/20 px-4 py-2 text-sm font-bold text-af-error hover:bg-af-error/30 disabled:opacity-50"
              >
                {actionBusy ? "…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </ToolShell>
  );
}
