"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
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
    <div className="space-y-6">
      <Link href="/finetune" className="text-sm text-neutral-500 hover:text-white">
        ← Fine-tune
      </Link>
      <h1 className="text-2xl font-semibold">New fine-tune job</h1>
      <p className="text-sm text-neutral-500">
        Creates a pending job record; training on Modal is Phase 07.
      </p>
      <label className="block text-sm text-neutral-400">Base model</label>
      <input
        value={baseModel}
        onChange={(e) => setBaseModel(e.target.value)}
        className="w-full max-w-lg rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
      />
      <label className="block text-sm text-neutral-400">Dataset path</label>
      <input
        value={datasetPath}
        onChange={(e) => setDatasetPath(e.target.value)}
        className="w-full max-w-lg rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
      />
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button
        type="button"
        disabled={busy}
        onClick={submit}
        className="rounded-md bg-cyan-500 px-4 py-2 text-sm font-medium text-black disabled:opacity-50"
      >
        {busy ? "Creating…" : "Create job"}
      </button>
    </div>
  );
}
