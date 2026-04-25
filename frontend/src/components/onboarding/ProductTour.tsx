"use client";

import { useCallback, useEffect, useState } from "react";

const STEPS: { selector: string; title?: string; body: string }[] = [
  {
    selector: '[data-tour="dashboard-title"]',
    title: "Dashboard",
    body: "Metrics for agents, executions, security scores, and quick actions.",
  },
  {
    selector: '[data-tour="onboarding-card"]',
    body: "Complete these steps once — progress is saved in your browser.",
  },
  {
    selector: '[data-tour="nav-agents"]',
    body: "Build and run agents from the Agents section.",
  },
];

type ProductTourProps = {
  run: boolean;
  onComplete: () => void;
};

export function ProductTour({ run, onComplete }: ProductTourProps) {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);

  const updateRect = useCallback(() => {
    if (!run || i >= STEPS.length) return;
    const el = document.querySelector(STEPS[i]?.selector ?? "");
    if (el) setRect(el.getBoundingClientRect());
    else setRect(null);
  }, [run, i]);

  useEffect(() => {
    updateRect();
  }, [updateRect]);

  useEffect(() => {
    if (!run) return;
    const onResize = () => updateRect();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [run, updateRect]);

  useEffect(() => {
    if (!run) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onComplete();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [run, onComplete]);

  useEffect(() => {
    if (!run) setI(0);
  }, [run]);

  if (!run || i >= STEPS.length) return null;

  return (
    <>
      <div className="fixed inset-0 z-[100] bg-black/50" aria-hidden />
      {rect && (
        <div
          className="pointer-events-none fixed z-[101] rounded-lg shadow-[0_0_0_9999px_rgba(0,0,0,0.55)] ring-2 ring-af-primary"
          style={{
            top: rect.top - 4,
            left: rect.left - 4,
            width: rect.width + 8,
            height: rect.height + 8,
          }}
        />
      )}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="product-tour-title"
        className="fixed bottom-8 left-1/2 z-[102] w-[min(100%-2rem,24rem)] -translate-x-1/2 rounded-xl border border-af-border bg-af-surface-container p-4 text-sm text-white shadow-xl"
      >
        <p id="product-tour-title" className="mb-2 font-bold text-af-on-surface">
          {STEPS[i].title ?? "Tip"}
        </p>
        <p className="text-af-muted">{STEPS[i].body}</p>
        <p className="mt-2 text-[10px] text-af-muted-dim">Press Esc to close</p>
        <div className="mt-3 flex justify-end gap-2">
          <button
            type="button"
            className="rounded-lg border border-af-border px-3 py-1.5 text-xs font-bold text-af-muted transition-colors hover:border-af-primary hover:text-af-primary"
            onClick={onComplete}
          >
            Skip
          </button>
          <button
            type="button"
            className="rounded-lg bg-af-primary px-3 py-1.5 text-xs font-bold text-white transition-opacity hover:opacity-90"
            onClick={() => {
              if (i + 1 >= STEPS.length) onComplete();
              else setI((x) => x + 1);
            }}
          >
            {i + 1 >= STEPS.length ? "Done" : "Next"}
          </button>
        </div>
      </div>
    </>
  );
}
