"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";

const BASE_MODELS = [
  "unsloth/llama-3.2-1b-instruct",
  "unsloth/llama-3.1-8b-instruct",
  "unsloth/mistral-7b-instruct-v0.3",
] as const;

export default function NewFinetunePage() {
  const router = useRouter();
  const [baseModel, setBaseModel] = useState<string>(BASE_MODELS[0]);
  const [datasetPath, setDatasetPath] = useState("hf://trl-lib/Capybara");
  const [epochs, setEpochs] = useState("1");
  const [learningRate, setLearningRate] = useState("0.0002");
  const [batchSize, setBatchSize] = useState("2");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    const ep = epochs.trim() ? Number.parseInt(epochs, 10) : undefined;
    const lr = learningRate.trim() ? Number.parseFloat(learningRate) : undefined;
    const bs = batchSize.trim() ? Number.parseInt(batchSize, 10) : undefined;
    if (ep !== undefined && (Number.isNaN(ep) || ep < 1)) {
      setError("Epochs must be a positive integer");
      setBusy(false);
      return;
    }
    if (lr !== undefined && Number.isNaN(lr)) {
      setError("Learning rate must be a number");
      setBusy(false);
      return;
    }
    if (bs !== undefined && (Number.isNaN(bs) || bs < 1)) {
      setError("Batch size must be a positive integer");
      setBusy(false);
      return;
    }
    try {
      await api("/api/v1/finetune", {
        method: "POST",
        body: JSON.stringify({
          base_model: baseModel,
          dataset_path: datasetPath,
          hyperparams: {
            ...(ep !== undefined ? { epochs: ep } : {}),
            ...(lr !== undefined ? { learning_rate: lr } : {}),
            ...(bs !== undefined ? { batch_size: bs } : {}),
          },
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
      <h1 className="mb-4 font-sans text-3xl font-bold text-white">Start training</h1>
      <p className="mb-8 max-w-xl text-sm text-af-muted">
        Queue a fine-tuning job. With <code className="text-af-primary">MODAL_ENABLED=false</code> jobs stay{" "}
        <strong className="text-af-on-surface">pending</strong>; enable Modal + deploy{" "}
        <code className="font-mono text-xs">modal_functions/train.py</code> for GPU runs.
      </p>
      <div className="af-card max-w-lg space-y-6 p-8">
        <div>
          <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
            Base model
          </label>
          <select
            value={baseModel}
            onChange={(e) => setBaseModel(e.target.value)}
            className="af-input w-full font-mono"
          >
            {BASE_MODELS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
            Dataset URL or path
          </label>
          <input
            value={datasetPath}
            onChange={(e) => setDatasetPath(e.target.value)}
            className="af-input font-mono"
            placeholder="hf://dataset/name or /mount/file.jsonl"
          />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Epochs
            </label>
            <input
              type="number"
              min={1}
              value={epochs}
              onChange={(e) => setEpochs(e.target.value)}
              className="af-input font-mono"
            />
          </div>
          <div>
            <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Learning rate
            </label>
            <input
              type="text"
              inputMode="decimal"
              value={learningRate}
              onChange={(e) => setLearningRate(e.target.value)}
              className="af-input font-mono"
            />
          </div>
          <div>
            <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Batch size
            </label>
            <input
              type="number"
              min={1}
              value={batchSize}
              onChange={(e) => setBatchSize(e.target.value)}
              className="af-input font-mono"
            />
          </div>
        </div>
        {error && <p className="text-sm text-af-error">{error}</p>}
        <button
          type="button"
          disabled={busy}
          onClick={submit}
          className="af-btn-primary flex w-full items-center justify-center gap-2 py-3 text-sm disabled:opacity-50"
        >
          {busy ? (
            <span className="material-symbols-outlined animate-spin text-lg">autorenew</span>
          ) : (
            "Start training"
          )}
        </button>
      </div>
    </ToolShell>
  );
}
