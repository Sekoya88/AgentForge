"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ONBOARDING_STEPS,
  dismissOnboarding,
  getCompletedSteps,
  isOnboardingDismissed,
} from "@/lib/onboarding";

export function OnboardingChecklist() {
  const [dismissed, setDismissed] = useState(true);
  const [completed, setCompleted] = useState<string[]>([]);

  useEffect(() => {
    setDismissed(isOnboardingDismissed());
    setCompleted(getCompletedSteps());
  }, []);

  if (dismissed) return null;

  const allDone = completed.length >= ONBOARDING_STEPS.length;

  function handleDismiss() {
    dismissOnboarding();
    setDismissed(true);
  }

  return (
    <section className="af-motion-fade-in mb-8 rounded-xl border border-af-primary/20 bg-af-surface-container/60 p-6 backdrop-blur-sm">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <span className="material-symbols-outlined text-base text-af-primary">rocket_launch</span>
            <span className="text-[10px] font-bold uppercase tracking-widest text-af-primary">
              Getting started
            </span>
          </div>
          <h2 className="text-lg font-bold text-af-on-surface">
            {allDone ? "You're all set 🎉" : "Set up AgentForge in 5 steps"}
          </h2>
        </div>
        <button
          type="button"
          onClick={handleDismiss}
          className="flex h-7 w-7 items-center justify-center rounded-md text-af-muted-dim transition-colors hover:text-af-on-surface"
          aria-label="Dismiss onboarding"
        >
          <span className="material-symbols-outlined text-base">close</span>
        </button>
      </div>

      {/* Progress bar */}
      <div className="mb-5 h-1.5 overflow-hidden rounded-full bg-af-border">
        <div
          className="h-full rounded-full bg-af-primary transition-all duration-500"
          style={{ width: `${(completed.length / ONBOARDING_STEPS.length) * 100}%` }}
        />
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {ONBOARDING_STEPS.map((step, i) => {
          const done = completed.includes(step.id);
          return (
            <div
              key={step.id}
              className={`flex items-start gap-3 rounded-lg border p-4 transition-colors ${
                done
                  ? "border-af-tertiary/20 bg-af-tertiary/5 opacity-70"
                  : "border-af-border/60 bg-af-surface-high/40 hover:border-af-primary/40"
              }`}
            >
              <div
                className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border ${
                  done
                    ? "border-af-tertiary/30 bg-af-tertiary/15 text-af-tertiary"
                    : "border-af-border/60 bg-af-surface-container text-af-muted"
                }`}
              >
                {done ? (
                  <span className="material-symbols-outlined text-base">check</span>
                ) : (
                  <span className="text-xs font-bold text-af-muted-dim">{i + 1}</span>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p className={`text-sm font-bold ${done ? "text-af-muted line-through" : "text-af-on-surface"}`}>
                  {step.label}
                </p>
                <p className="mt-0.5 text-xs leading-relaxed text-af-muted">{step.description}</p>
                {!done && (
                  <Link
                    href={step.href}
                    className="mt-2 inline-flex items-center gap-1 text-xs font-bold text-af-primary hover:underline"
                  >
                    {step.cta}
                    <span className="material-symbols-outlined text-sm">arrow_forward</span>
                  </Link>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {allDone && (
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={handleDismiss}
            className="rounded-lg border border-af-tertiary/40 bg-af-tertiary/10 px-4 py-2 text-sm font-bold text-af-tertiary transition-colors hover:bg-af-tertiary/20"
          >
            Dismiss checklist
          </button>
        </div>
      )}
    </section>
  );
}
