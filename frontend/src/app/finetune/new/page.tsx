"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";

const POPULAR_MODELS = [
  { value: "TinyLlama/TinyLlama-1.1B-Chat-v1.0", label: "TinyLlama 1.1B Chat", size: "1.1B", speed: "fast" },
  { value: "unsloth/llama-3.2-1b-instruct", label: "Llama 3.2 1B Instruct", size: "1B", speed: "fast" },
  { value: "unsloth/llama-3.2-3b-instruct", label: "Llama 3.2 3B Instruct", size: "3B", speed: "medium" },
  { value: "unsloth/Phi-4-mini-instruct", label: "Phi-4 Mini Instruct", size: "3.8B", speed: "medium" },
  { value: "unsloth/gemma-3-1b-it", label: "Gemma 3 1B IT", size: "1B", speed: "fast" },
  { value: "unsloth/gemma-3-4b-it", label: "Gemma 3 4B IT", size: "4B", speed: "medium" },
  { value: "unsloth/Qwen2.5-1.5B-Instruct", label: "Qwen 2.5 1.5B Instruct", size: "1.5B", speed: "fast" },
  { value: "unsloth/Qwen2.5-3B-Instruct", label: "Qwen 2.5 3B Instruct", size: "3B", speed: "medium" },
  { value: "unsloth/llama-3.1-8b-instruct", label: "Llama 3.1 8B Instruct", size: "8B", speed: "slow" },
  { value: "unsloth/mistral-7b-instruct-v0.3", label: "Mistral 7B Instruct v0.3", size: "7B", speed: "slow" },
  { value: "unsloth/Phi-4", label: "Phi-4", size: "14B", speed: "slow" },
] as const;

const SPEED_BADGE: Record<string, string> = {
  fast: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  medium: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  slow: "border-af-error/30 bg-af-error/10 text-af-error",
};

export default function NewFinetunePage() {
  const router = useRouter();
  const [baseModel, setBaseModel] = useState<string>(POPULAR_MODELS[0].value);
  const [customModel, setCustomModel] = useState("");
  const [useCustom, setUseCustom] = useState(false);
  const [datasetPath, setDatasetPath] = useState("hf://trl-lib/Capybara");
  const [epochs, setEpochs] = useState("");
  const [maxSteps, setMaxSteps] = useState("30");
  const [learningRate, setLearningRate] = useState("0.0002");
  const [batchSize, setBatchSize] = useState("2");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const customRef = useRef<HTMLInputElement>(null);

  const resolvedModel = useCustom ? customModel.trim() : baseModel;

  async function submit() {
    setBusy(true);
    setError(null);
    if (!resolvedModel) {
      setError("Please select or enter a model name");
      setBusy(false);
      return;
    }
    const ep = epochs.trim() ? Number.parseInt(epochs, 10) : undefined;
    const ms = maxSteps.trim() ? Number.parseInt(maxSteps, 10) : undefined;
    const lr = learningRate.trim() ? Number.parseFloat(learningRate) : undefined;
    const bs = batchSize.trim() ? Number.parseInt(batchSize, 10) : undefined;
    if (ep !== undefined && (Number.isNaN(ep) || ep < 1)) {
      setError("Epochs must be a positive integer");
      setBusy(false);
      return;
    }
    if (ms !== undefined && (Number.isNaN(ms) || ms < 1)) {
      setError("Max steps must be a positive integer");
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
          base_model: resolvedModel,
          dataset_path: datasetPath,
          hyperparams: {
            ...(ep !== undefined ? { epochs: ep } : {}),
            ...(ms !== undefined ? { max_steps: ms } : {}),
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
      <div className="af-card max-w-2xl space-y-6 p-8">
        {/* Model selection */}
        <div>
          <div className="mb-3 flex items-center justify-between">
            <label className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Base model
            </label>
            <button
              type="button"
              onClick={() => {
                setUseCustom(!useCustom);
                if (!useCustom) setTimeout(() => customRef.current?.focus(), 50);
              }}
              className="text-[10px] font-bold text-af-primary hover:text-af-primary/80"
            >
              {useCustom ? "← Back to list" : "Custom model ID"}
            </button>
          </div>

          {useCustom ? (
            <div>
              <input
                ref={customRef}
                value={customModel}
                onChange={(e) => setCustomModel(e.target.value)}
                className="af-input w-full font-mono"
                placeholder="org/model-name  (e.g. meta-llama/Llama-3.2-1B-Instruct)"
              />
              <p className="mt-2 text-[11px] leading-relaxed text-af-muted-dim">
                Use the exact HuggingFace model ID: <code className="text-af-muted">org/model-name</code>.
                Find models at{" "}
                <a href="https://huggingface.co/models?sort=trending&search=instruct" target="_blank" rel="noreferrer" className="text-af-primary hover:underline">
                  huggingface.co/models
                </a>
                . For Unsloth-optimized 4bit versions, prefix with <code className="text-af-muted">unsloth/</code> (e.g. <code className="text-af-muted">unsloth/llama-3.2-1b-instruct</code>).
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-2">
              {POPULAR_MODELS.map((m) => (
                <button
                  key={m.value}
                  type="button"
                  onClick={() => setBaseModel(m.value)}
                  className={`flex items-center justify-between rounded-lg border px-4 py-3 text-left text-sm transition-all ${
                    baseModel === m.value
                      ? "border-af-primary/50 bg-af-primary/10 text-af-on-surface"
                      : "border-af-border/40 bg-af-surface-low text-af-muted hover:border-af-border/80 hover:text-af-on-surface"
                  }`}
                >
                  <div className="min-w-0">
                    <span className="font-bold">{m.label}</span>
                    <span className="ml-2 font-mono text-[10px] text-af-muted-dim">{m.value}</span>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="rounded bg-af-surface-high px-2 py-0.5 font-mono text-[10px] font-bold text-af-muted">
                      {m.size}
                    </span>
                    <span className={`rounded-full border px-2 py-0.5 text-[9px] font-bold ${SPEED_BADGE[m.speed]}`}>
                      {m.speed}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Dataset */}
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
          <p className="mt-1.5 text-[11px] text-af-muted-dim">
            HuggingFace: <code className="text-af-muted">hf://org/dataset</code> · Supports: text, messages/conversations (chat), Alpaca (instruction/input/output)
          </p>
        </div>

        {/* Hyperparams */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
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
              placeholder="—"
            />
            <p className="mt-1 text-[10px] text-af-muted-dim">Overrides max steps</p>
          </div>
          <div>
            <label className="mb-2 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Max steps
            </label>
            <input
              type="number"
              min={1}
              value={maxSteps}
              onChange={(e) => setMaxSteps(e.target.value)}
              className="af-input font-mono"
              placeholder="30"
            />
            <p className="mt-1 text-[10px] text-af-muted-dim">Used if epochs empty</p>
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
          disabled={busy || !resolvedModel}
          onClick={submit}
          className="af-btn-primary flex w-full items-center justify-center gap-2 py-3 text-sm disabled:opacity-50"
        >
          {busy ? (
            <span className="material-symbols-outlined animate-spin text-lg">autorenew</span>
          ) : (
            <>
              <span className="material-symbols-outlined text-lg">rocket_launch</span>
              Start training
            </>
          )}
        </button>
      </div>
    </ToolShell>
  );
}
