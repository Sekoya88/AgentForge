// frontend/src/components/agent/AgentActivityIcon.tsx
"use client";

import { AgentStep } from "@/types/chat";

type Props = {
  event: AgentStep["event"] | "agent_start";
  size?: number;
};

/**
 * Renders an animated SVG icon for a given agent event type.
 * All animations are pure CSS @keyframes — no JS animation library.
 */
export function AgentActivityIcon({ event, size = 28 }: Props) {
  const s = size;
  const r = Math.round(s * 0.32); // border-radius

  const wrap = (bg: string, content: React.ReactNode) => (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: s,
        height: s,
        borderRadius: r,
        background: bg,
        flexShrink: 0,
      }}
    >
      {content}
    </span>
  );

  if (event === "agent_start") {
    return wrap(
      "#2d1f3d",
      <>
        <style>{`
          @keyframes af-spin { to { transform: rotate(360deg); } }
        `}</style>
        <svg width={s * 0.55} height={s * 0.55} viewBox="0 0 20 20" fill="none">
          <circle cx="10" cy="10" r="8" stroke="#c084fc" strokeWidth="2" strokeDasharray="28 8"
            style={{ animation: "af-spin 1.5s linear infinite", transformOrigin: "center" }} />
        </svg>
      </>
    );
  }

  if (event === "tool_call") {
    return wrap(
      "#1e3a5f",
      <>
        <style>{`
          @keyframes af-wrench {
            0%,100% { transform: rotate(0deg); }
            25%      { transform: rotate(-18deg); }
            75%      { transform: rotate(18deg); }
          }
        `}</style>
        <svg width={s * 0.55} height={s * 0.55} viewBox="0 0 20 20" fill="none"
          style={{ animation: "af-wrench 0.7s ease-in-out infinite" }}>
          <path d="M12.5 2a5.5 5.5 0 0 0-5.18 7.37L2 14.75 3.25 16l5.38-5.32A5.5 5.5 0 1 0 12.5 2zm0 9a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z"
            fill="#60a5fa" />
        </svg>
      </>
    );
  }

  if (event === "skill") {
    return wrap(
      "#1a3320",
      <svg width={s * 0.55} height={s * 0.55} viewBox="0 0 20 20" fill="none">
        <rect x="3" y="2" width="14" height="16" rx="2" stroke="#4ade80" strokeWidth="1.8" fill="none" />
        <line x1="6" y1="7" x2="14" y2="7" stroke="#4ade80" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="6" y1="10" x2="14" y2="10" stroke="#4ade80" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="6" y1="13" x2="11" y2="13" stroke="#4ade80" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }

  if (event === "complete") {
    return wrap(
      "#0f2d1f",
      <>
        <style>{`
          @keyframes af-fadein { from { opacity: 0; transform: scale(0.7); } to { opacity: 1; transform: scale(1); } }
        `}</style>
        <svg width={s * 0.55} height={s * 0.55} viewBox="0 0 20 20" fill="none"
          style={{ animation: "af-fadein 0.3s ease" }}>
          <path d="M4 10l5 5 7-8" stroke="#4ade80" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </>
    );
  }

  if (event === "error") {
    return wrap(
      "#2d1010",
      <>
        <style>{`
          @keyframes af-shake {
            0%,100% { transform: translateX(0); }
            20%      { transform: translateX(-3px); }
            60%      { transform: translateX(3px); }
          }
        `}</style>
        <svg width={s * 0.55} height={s * 0.55} viewBox="0 0 20 20" fill="none"
          style={{ animation: "af-shake 0.4s ease" }}>
          <path d="M10 4v7M10 14v1" stroke="#f87171" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
      </>
    );
  }

  // interrupt — person + pause + alert ring
  return wrap(
    "#2d1020",
    <>
      <style>{`
        @keyframes af-pulse-ring {
          0%   { transform: scale(1); opacity: 0.7; }
          100% { transform: scale(2.2); opacity: 0; }
        }
        @keyframes af-alert { 0%,100%{opacity:1} 50%{opacity:.25} }
      `}</style>
      <span style={{ position: "relative", display: "inline-flex", alignItems: "center", justifyContent: "center", width: s * 0.7, height: s * 0.7 }}>
        <span style={{
          position: "absolute", inset: -2, borderRadius: "50%",
          border: "1.5px solid #f87171",
          animation: "af-pulse-ring 1.4s ease-out infinite",
        }} />
        <svg width={s * 0.6} height={s * 0.6} viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="6" r="3.5" fill="#c084fc" />
          <path d="M5 20c0-3.866 3.134-7 7-7s7 3.134 7 7" stroke="#c084fc" strokeWidth="1.8" strokeLinecap="round" fill="none" />
          <rect x="8.5" y="9" width="2.5" height="8" rx="1.2" fill="#2d1020" />
          <rect x="13" y="9" width="2.5" height="8" rx="1.2" fill="#2d1020" />
          <circle cx="19" cy="5" r="3" fill="#f87171" style={{ animation: "af-alert 0.9s infinite" }} />
          <text x="19" y="7.5" textAnchor="middle" fontSize="4.5" fill="white" fontWeight="bold">!</text>
        </svg>
      </span>
    </>
  );
}

/** Waveform bars: used for "generating response" (token stream active) */
export function WaveformIcon({ color = "#4ade80", height = 20 }: { color?: string; height?: number }) {
  const bars = [0.4, 0.75, 1, 0.85, 0.6, 0.45];
  return (
    <>
      <style>{`
        @keyframes af-wave {
          0%,100% { transform: scaleY(0.35); }
          50%      { transform: scaleY(1); }
        }
      `}</style>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 2, height }}>
        {bars.map((h, i) => (
          <span key={i} style={{
            width: 3,
            height: height * h,
            borderRadius: 2,
            background: color,
            display: "block",
            animation: `af-wave 1s ${i * 0.1}s ease-in-out infinite`,
            transformOrigin: "bottom",
          }} />
        ))}
      </span>
    </>
  );
}
