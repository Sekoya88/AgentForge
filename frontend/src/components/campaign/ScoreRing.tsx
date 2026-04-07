// frontend/src/components/campaign/ScoreRing.tsx
"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  score: number; // 0–100
  size?: number;
};

function ringColor(score: number): string {
  if (score >= 80) return "#34d399"; // emerald-400
  if (score >= 50) return "#fbbf24"; // amber-400
  return "#f87171"; // red-400
}

const DURATION = 800; // ms

export function ScoreRing({ score, size = 120 }: Props) {
  const [displayScore, setDisplayScore] = useState(0);
  const rafRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);

  useEffect(() => {
    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (prefersReduced) {
      setDisplayScore(score);
      return;
    }

    // Reset to 0 on each score change to restart animation
    setDisplayScore(0);
    startTimeRef.current = null;

    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
    }

    const animate = (timestamp: number) => {
      if (startTimeRef.current === null) {
        startTimeRef.current = timestamp;
      }

      const elapsed = timestamp - startTimeRef.current;
      const t = Math.min(elapsed / DURATION, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      const current = eased * score;

      setDisplayScore(current);

      if (t < 1) {
        rafRef.current = requestAnimationFrame(animate);
      } else {
        setDisplayScore(score);
        rafRef.current = null;
      }
    };

    rafRef.current = requestAnimationFrame(animate);

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [score]);

  const r = (size - 16) / 2;
  const circumference = 2 * Math.PI * r;
  const progress = Math.max(0, Math.min(100, displayScore));
  const strokeDashoffset = circumference - (progress / 100) * circumference;
  const color = ringColor(displayScore);

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
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-2xl font-bold text-white" style={{ color }}>
          {Math.round(displayScore)}
        </span>
        <span className="text-[9px] font-bold uppercase tracking-widest text-af-muted-dim">
          score
        </span>
      </div>
    </div>
  );
}
