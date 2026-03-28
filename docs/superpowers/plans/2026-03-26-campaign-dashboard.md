# Campaign Dashboard Improvements Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the campaign detail page with: a visual score ring gauge, severity-categorized vulnerability display, and a "Download report" JSON export button. The current page shows raw numbers but lacks visual hierarchy for security decision-making.

**Architecture:** All changes are in `frontend/src/app/campaigns/[id]/page.tsx` (client component). No backend changes needed. The score ring is a pure SVG. Vulnerabilities are re-categorized by severity (high/medium/low) based on keywords in the key name. Export is a client-side JSON blob download.

**Tech Stack:** React, TypeScript, SVG, existing design tokens (`af-*` CSS classes).

---

### Task 1: Add score ring gauge component

**Files:**
- Create: `frontend/src/components/campaign/ScoreRing.tsx`

- [ ] **Step 1: Create the SVG ring component**

```tsx
// frontend/src/components/campaign/ScoreRing.tsx
"use client";

type Props = {
  score: number; // 0–100
  size?: number;
};

function ringColor(score: number): string {
  if (score >= 80) return "#34d399"; // emerald-400
  if (score >= 50) return "#fbbf24"; // amber-400
  return "#f87171"; // red-400
}

export function ScoreRing({ score, size = 120 }: Props) {
  const r = (size - 16) / 2;
  const circumference = 2 * Math.PI * r;
  const progress = Math.max(0, Math.min(100, score));
  const strokeDashoffset = circumference - (progress / 100) * circumference;
  const color = ringColor(score);

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        {/* Background ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={8}
        />
        {/* Progress ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          style={{ transition: "stroke-dashoffset 0.6s ease-in-out" }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-2xl font-bold text-white" style={{ color }}>
          {Math.round(score)}
        </span>
        <span className="text-[9px] font-bold uppercase tracking-widest text-af-muted-dim">
          score
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd frontend && git add src/components/campaign/ScoreRing.tsx
git commit -m "feat(ui): add ScoreRing SVG component for campaign score visualization"
```

---

### Task 2: Add vulnerability severity categorization

**Files:**
- Modify: `frontend/src/app/campaigns/[id]/page.tsx`

- [ ] **Step 1: Add severity detection helper and ScoreRing import**

At the top of `frontend/src/app/campaigns/[id]/page.tsx`, add the import:

```tsx
import { ScoreRing } from "@/components/campaign/ScoreRing";
```

Inside the component, after the existing `const vulnEntries = ...` line, add:

```tsx
type VulnSeverity = "high" | "medium" | "low";

function vulnSeverity(key: string): VulnSeverity {
  const k = key.toLowerCase();
  if (/inject|jailbreak|hijack|prompt.inject|shell|rce|sqli|xss/i.test(k)) return "high";
  if (/bias|disclosure|leak|bypass|pii/i.test(k)) return "medium";
  return "low";
}

const severityOrder: VulnSeverity[] = ["high", "medium", "low"];
const severityLabel: Record<VulnSeverity, string> = {
  high: "Critical / High",
  medium: "Medium",
  low: "Low / Informational",
};
const severityStyles: Record<VulnSeverity, string> = {
  high: "border-red-500/30 bg-red-500/5",
  medium: "border-amber-500/30 bg-amber-500/5",
  low: "border-white/10 bg-white/3",
};
const severityBadge: Record<VulnSeverity, string> = {
  high: "bg-red-500/20 text-red-400",
  medium: "bg-amber-500/20 text-amber-400",
  low: "bg-white/10 text-af-muted",
};

const vulnBySeverity = severityOrder.reduce<Record<VulnSeverity, [string, unknown][]>>(
  (acc, sev) => {
    acc[sev] = vulnEntries.filter(([k]) => vulnSeverity(k) === sev);
    return acc;
  },
  { high: [], medium: [], low: [] },
);
```

- [ ] **Step 2: Replace the score overview section**

Find the existing `{/* Score overview */}` section in the JSX (the `<section className="mt-8 grid gap-4 sm:grid-cols-4">` block) and replace it with:

```tsx
{/* Score overview */}
<section className="mt-8 flex flex-wrap items-center gap-6">
  {c.overall_score != null && (
    <ScoreRing score={c.overall_score} size={130} />
  )}
  <div className="grid grid-cols-3 gap-4 flex-1">
    <div className="af-card p-4 text-center">
      <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">Total</p>
      <p className="mt-2 text-2xl font-bold text-white">{c.total_tests ?? "—"}</p>
      <p className="text-xs text-af-muted">tests</p>
    </div>
    <div className="af-card p-4 text-center">
      <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">Passed</p>
      <p className="mt-2 text-2xl font-bold text-emerald-400">{c.passed_tests ?? "—"}</p>
      {passRate != null && <p className="text-xs text-af-muted">{passRate}%</p>}
    </div>
    <div className="af-card p-4 text-center">
      <p className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">Failed</p>
      <p className="mt-2 text-2xl font-bold text-red-400">{c.failed_tests ?? "—"}</p>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Replace the vulnerabilities section**

Find the existing `{/* Vulnerabilities */}` section and replace it with:

```tsx
{/* Vulnerabilities by severity */}
{vulnEntries.length > 0 && (
  <section className="mt-8">
    <h2 className="mb-4 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
      Vulnerabilities ({vulnEntries.length})
    </h2>
    <div className="space-y-6">
      {severityOrder.map((sev) => {
        const entries = vulnBySeverity[sev];
        if (entries.length === 0) return null;
        return (
          <div key={sev}>
            <p className="mb-2 text-xs font-semibold text-af-muted">
              {severityLabel[sev]} ({entries.length})
            </p>
            <div className="space-y-2">
              {entries.map(([key, val]) => (
                <div key={key} className={`rounded-lg border p-4 ${severityStyles[sev]}`}>
                  <div className="flex items-center gap-2">
                    <span className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase ${severityBadge[sev]}`}>
                      {sev}
                    </span>
                    <span className="font-mono text-sm font-medium text-white">{key}</span>
                  </div>
                  <pre className="mt-2 overflow-x-auto text-xs text-af-muted">
                    {typeof val === "string" ? val : JSON.stringify(val, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  </section>
)}
```

- [ ] **Step 4: Add export button next to the Delete button**

Find the Delete button in the JSX header section and add an Export button next to it:

```tsx
<div className="flex gap-2">
  <button
    type="button"
    onClick={() => {
      const blob = new Blob([JSON.stringify(c, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `campaign-${c.id.slice(0, 8)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    }}
    className="rounded-lg border border-af-border/30 bg-af-surface-low px-4 py-2 text-sm text-af-muted hover:text-white"
  >
    Export JSON
  </button>
  <button
    type="button"
    onClick={del}
    disabled={deleting}
    className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-400 hover:bg-red-500/20 disabled:opacity-50"
  >
    Delete
  </button>
</div>
```

- [ ] **Step 5: Verify TypeScript compilation**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No type errors.

- [ ] **Step 6: Commit**

```bash
cd frontend && git add src/app/campaigns/\[id\]/page.tsx src/components/campaign/
git commit -m "feat(ui): enhance campaign dashboard with score ring, severity grouping, and JSON export"
```
