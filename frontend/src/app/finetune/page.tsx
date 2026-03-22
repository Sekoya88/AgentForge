"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";

type Job = {
  id: string;
  base_model: string;
  status: string;
  inference_endpoint: string | null;
};

function jobStatusStyle(status: string) {
  const s = status.toLowerCase();
  if (s.includes("run") || s.includes("progress"))
    return "border-af-tertiary/20 bg-af-tertiary/10 text-af-tertiary";
  if (s.includes("complete") || s.includes("done"))
    return "border-white/10 bg-white/5 text-af-muted";
  return "border-af-secondary/20 bg-af-secondary/10 text-af-secondary";
}

export default function FinetunePage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const data = await api<Job[]>("/api/v1/finetune");
        if (!c) setJobs(data);
      } catch (e) {
        if (!c) {
          if (e instanceof ApiError && e.status === 401) router.push("/login");
          else setError(e instanceof Error ? e.message : "Failed");
        }
      }
    })();
    return () => {
      c = true;
    };
  }, [router]);

  return (
    <ToolShell active="finetune">
      <header className="mb-12">
        <div className="mb-2 flex items-center gap-2">
          <span className="text-[10px] font-bold tracking-[0.3em] text-af-primary uppercase">
            [ FINE-TUNE ]
          </span>
          <div className="h-px w-12 bg-af-primary/30" />
        </div>
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div>
            <h1 className="font-sans text-4xl tracking-tighter text-af-on-surface md:text-6xl">
              Model <span className="af-serif-italic">refinement</span>
            </h1>
            <p className="mt-4 max-w-xl text-sm leading-relaxed text-af-muted">
              Job records for LoRA / full tuning; Modal training hooks land in later phases.
            </p>
          </div>
          <Link
            href="/finetune/new"
            className="af-btn-primary inline-flex items-center gap-2 px-8 py-4 text-sm"
          >
            <span className="material-symbols-outlined">add_circle</span>
            New Job
          </Link>
        </div>
      </header>

      <div className="mb-12 grid grid-cols-1 gap-6 md:grid-cols-4">
        {[
          ["Jobs", jobs?.length ?? "—"],
          ["Pending", jobs?.filter((j) => j.status.toLowerCase().includes("pend")).length ?? "—"],
          ["With endpoint", jobs?.filter((j) => j.inference_endpoint).length ?? "—"],
          ["Stack", "Modal"],
        ].map(([k, v]) => (
          <div key={String(k)} className="rounded-lg border border-af-border/40 bg-af-surface-container p-6">
            <p className="mb-2 text-[10px] uppercase tracking-wider text-af-muted-dim">{k}</p>
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
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-af-surface-high border border-af-border/80 text-af-muted">
            <span className="material-symbols-outlined text-3xl">tune</span>
          </div>
          <h3 className="mb-2 font-bold text-white text-lg">No fine-tuning jobs yet</h3>
          <p className="mb-6 max-w-sm text-sm text-af-muted">
            Start a new fine-tuning job to adapt base models to your specific domain and use cases.
          </p>
          <Link
            href="/finetune/new"
            className="af-btn-primary px-6 py-2.5 text-sm"
          >
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
          {jobs.map((j) => (
            <div
              key={j.id}
              className="rounded-xl border border-transparent bg-af-surface-container p-1 transition-all hover:border-af-indigo/20"
            >
              <div className="flex flex-col gap-4 rounded-lg bg-af-surface-low p-6 md:flex-row md:items-center md:justify-between">
                <div>
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
                  {j.inference_endpoint && (
                    <p className="truncate font-mono text-xs text-af-muted">{j.inference_endpoint}</p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </ToolShell>
  );
}
