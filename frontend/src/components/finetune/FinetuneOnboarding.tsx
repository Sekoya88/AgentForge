"use client";

interface Props {
  onDismiss: () => void;
  onStart: () => void;
}

const STEPS = [
  {
    icon: "🧠",
    title: "What is fine-tuning?",
    body: "Fine-tuning adapts a pre-trained LLM to your specific domain, tone, or task. You provide examples of ideal inputs and outputs — the model learns your patterns without you writing a single prompt.",
  },
  {
    icon: "📄",
    title: "Prepare your training data",
    body: "AgentForge accepts JSONL files. Each line is one example: {\"messages\": [{\"role\": \"user\", \"content\": \"...\"}, {\"role\": \"assistant\", \"content\": \"...\"}]}. Aim for at least 50 high-quality examples.",
  },
  {
    icon: "⚡",
    title: "What you can fine-tune",
    body: "LLM models (GPT-4o Mini, Llama 3) for custom behavior, or speech models (ElevenLabs) for voice cloning. Each job runs on Modal and reports live metrics as it trains.",
  },
];

export function FinetuneOnboarding({ onDismiss, onStart }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="af-card w-full max-w-2xl mx-4 p-8 flex flex-col gap-8">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs af-text-muted uppercase tracking-widest mb-1">Fine-tuning</p>
            <h2 className="text-2xl font-semibold af-text-primary">Train models on your data</h2>
            <p className="text-sm af-text-muted mt-2">
              You have no fine-tuning jobs yet. Here&apos;s how it works.
            </p>
          </div>
          <button
            type="button"
            onClick={onDismiss}
            className="text-xs af-text-muted hover:af-text-primary transition-colors mt-1"
          >
            Skip
          </button>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {STEPS.map((s) => (
            <div
              key={s.title}
              className="flex flex-col gap-2 p-4 rounded-lg border"
              style={{ borderColor: "var(--af-border)", background: "var(--af-surface)" }}
            >
              <span className="text-2xl">{s.icon}</span>
              <p className="text-sm font-semibold af-text-primary">{s.title}</p>
              <p className="text-xs af-text-muted leading-relaxed">{s.body}</p>
            </div>
          ))}
        </div>

        <div className="border-t pt-6 flex items-center justify-between" style={{ borderColor: "var(--af-border)" }}>
          <div className="text-xs af-text-muted max-w-xs">
            A typical fine-tune job takes 10–30 minutes. You&apos;ll see live loss metrics as it trains.
          </div>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onDismiss}
              className="px-4 py-2 text-sm af-text-muted hover:af-text-primary transition-colors"
            >
              Maybe later
            </button>
            <button
              type="button"
              onClick={onStart}
              className="af-btn-primary px-6 py-2 text-sm"
            >
              Create first job →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
