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
