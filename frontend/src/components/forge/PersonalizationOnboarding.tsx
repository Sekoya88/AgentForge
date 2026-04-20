"use client";

import { useState } from "react";
import { updatePreferences } from "@/lib/user-preferences";

interface Props {
  onComplete: () => void;
  onSkip: () => void;
}

type Answers = {
  role: string;
  experience_level: string;
  primary_languages: string[];
  use_cases: string[];
  response_style: string;
  custom_context: string;
};

const ROLES = [
  { value: "developer", label: "Software Developer" },
  { value: "ml_engineer", label: "ML / AI Engineer" },
  { value: "data_scientist", label: "Data Scientist" },
  { value: "researcher", label: "Researcher" },
  { value: "product_manager", label: "Product Manager" },
  { value: "other", label: "Other" },
];

const EXPERIENCE_LEVELS = [
  { value: "beginner", label: "Beginner — new to AI/LLMs" },
  { value: "intermediate", label: "Intermediate — built some AI features" },
  { value: "expert", label: "Expert — shipping AI products in production" },
];

const LANGUAGES = ["Python", "TypeScript", "JavaScript", "Go", "Rust", "Java", "C++", "Other"];

const USE_CASES = [
  "Build agents",
  "Fine-tune models",
  "RAG / Knowledge base",
  "Security testing",
  "Automation / scheduling",
  "Voice assistants",
  "Code generation",
];

const RESPONSE_STYLES = [
  { value: "concise", label: "Concise — short, direct answers" },
  { value: "detailed", label: "Detailed — thorough explanations" },
  { value: "educational", label: "Educational — teach me the concepts" },
];

export function PersonalizationOnboarding({ onComplete, onSkip }: Props) {
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [answers, setAnswers] = useState<Answers>({
    role: "",
    experience_level: "",
    primary_languages: [],
    use_cases: [],
    response_style: "",
    custom_context: "",
  });

  const steps = [
    {
      title: "What's your primary role?",
      field: "role" as const,
      type: "single" as const,
      options: ROLES,
    },
    {
      title: "What's your experience level with AI?",
      field: "experience_level" as const,
      type: "single" as const,
      options: EXPERIENCE_LEVELS,
    },
    {
      title: "Which languages do you use most?",
      field: "primary_languages" as const,
      type: "multi" as const,
      options: LANGUAGES.map((l) => ({ value: l, label: l })),
    },
    {
      title: "What are your main use cases on AgentForge?",
      field: "use_cases" as const,
      type: "multi" as const,
      options: USE_CASES.map((u) => ({ value: u, label: u })),
    },
    {
      title: "How should I respond?",
      field: "response_style" as const,
      type: "single" as const,
      options: RESPONSE_STYLES,
    },
    {
      title: "Anything else I should know about your work?",
      field: "custom_context" as const,
      type: "text" as const,
      options: [],
    },
  ];

  const current = steps[step];
  const isLast = step === steps.length - 1;

  function toggleMulti(field: "primary_languages" | "use_cases", value: string) {
    setAnswers((prev) => {
      const arr = prev[field];
      return {
        ...prev,
        [field]: arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value],
      };
    });
  }

  async function handleFinish() {
    setSaving(true);
    try {
      await updatePreferences({
        ...answers,
        onboarding_completed: true,
      });
      onComplete();
    } finally {
      setSaving(false);
    }
  }

  function handleNext() {
    if (isLast) {
      handleFinish();
    } else {
      setStep((s) => s + 1);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="af-card w-full max-w-lg mx-4 p-8 flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs af-text-muted uppercase tracking-widest mb-1">
              Personalizing Forge · {step + 1} / {steps.length}
            </p>
            <h2 className="text-xl font-semibold af-text-primary">{current.title}</h2>
          </div>
          <button
            onClick={onSkip}
            className="text-xs af-text-muted hover:af-text-primary transition-colors"
          >
            Skip setup
          </button>
        </div>

        <div className="w-full h-1 rounded-full overflow-hidden" style={{ background: "var(--af-surface)" }}>
          <div
            className="h-full transition-all duration-300"
            style={{
              width: `${((step + 1) / steps.length) * 100}%`,
              background: "var(--af-accent)",
            }}
          />
        </div>

        {current.type === "single" && (
          <div className="flex flex-col gap-2">
            {current.options.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setAnswers((prev) => ({ ...prev, [current.field]: opt.value }))}
                className="text-left px-4 py-3 rounded-lg border transition-all"
                style={{
                  borderColor:
                    answers[current.field] === opt.value
                      ? "var(--af-accent)"
                      : "var(--af-border)",
                  background:
                    answers[current.field] === opt.value
                      ? "color-mix(in srgb, var(--af-accent) 10%, transparent)"
                      : "transparent",
                  color:
                    answers[current.field] === opt.value
                      ? "var(--af-accent)"
                      : "var(--af-text-secondary)",
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}

        {current.type === "multi" && (
          <div className="flex flex-wrap gap-2">
            {current.options.map((opt) => {
              const field = current.field as "primary_languages" | "use_cases";
              const selected = (answers[field] as string[]).includes(opt.value);
              return (
                <button
                  key={opt.value}
                  onClick={() => toggleMulti(field, opt.value)}
                  className="px-3 py-2 rounded-lg border text-sm transition-all"
                  style={{
                    borderColor: selected ? "var(--af-accent)" : "var(--af-border)",
                    background: selected
                      ? "color-mix(in srgb, var(--af-accent) 10%, transparent)"
                      : "transparent",
                    color: selected ? "var(--af-accent)" : "var(--af-text-secondary)",
                  }}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        )}

        {current.type === "text" && (
          <textarea
            value={answers.custom_context}
            onChange={(e) => setAnswers((prev) => ({ ...prev, custom_context: e.target.value }))}
            placeholder="e.g. I'm building a customer support agent for an e-commerce platform using Python and LangGraph."
            rows={4}
            className="af-input resize-none w-full"
          />
        )}

        <div className="flex items-center justify-between pt-2">
          <button
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0}
            className="text-sm af-text-muted hover:af-text-primary disabled:opacity-30 transition-colors"
          >
            ← Back
          </button>
          <button
            onClick={handleNext}
            disabled={saving}
            className="af-btn-primary px-6 py-2 text-sm"
          >
            {saving ? "Saving…" : isLast ? "Finish setup" : "Next →"}
          </button>
        </div>
      </div>
    </div>
  );
}
