"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";

export default function NewFinetunePage() {
  const router = useRouter();
  const [baseModel, setBaseModel] = useState("Qwen/Qwen2.5-7B");
  const [datasetPath, setDatasetPath] = useState("/data/train.jsonl");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api("/api/v1/finetune", {
        method: "POST",
        body: JSON.stringify({
          base_model: baseModel,
          dataset_path: datasetPath,
          hyperparams: { lora_rank: 16, epochs: 1 },
        }),
      });
      router.push("/finetune");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ToolShell active="finetune">
      <Link href="/finetune" className="mb-6 inline-block text-sm text-af-muted hover:text-af-primary">
        ← Fine-tune
      </Link>
      <span className="af-kicker mb-2 block">[ NEW JOB ]</span>
      <h1 className="mb-4 font-sans text-3xl font-bold text-white">Queue training</h1>
      <p className="mb-8 max-w-xl text-sm text-af-muted">
        Creates a pending job record; full Modal training is wired in backend phases.
      </p>
      <div className="af-card max-w-lg space-y-6 p-8">
        <div>
          <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
            Base model
          </label>
          <input
            value={baseModel}
            onChange={(e) => setBaseModel(e.target.value)}
            className="af-input font-mono"
          />
        </div>
        <div>
          <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
            Dataset path
          </label>
          <input
            value={datasetPath}
            onChange={(e) => setDatasetPath(e.target.value)}
            className="af-input font-mono"
          />
        </div>
        {error && <p className="text-sm text-af-error">{error}</p>}
        <button
          type="button"
          disabled={busy}
          onClick={submit}
          className="af-btn-primary w-full justify-center py-3 text-sm disabled:opacity-50"
        >
          {busy ? "Creating…" : "Create job"}
        </button>
      </div>
    </ToolShell>
  );
}
