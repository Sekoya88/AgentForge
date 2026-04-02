"use client";

import { useEffect, useRef } from "react";

// 10-level brightness ramp — space = empty, @ = brightest
const RAMP = " .·,:;+=*#@";

interface Attractor {
  phase: number;
  speed: number;
  // Lissajous amplitude/frequency for x and y (normalized 0–1)
  ax: number;
  fx: number;
  px: number;
  ay: number;
  fy: number;
  py: number;
  // Blob radius (in grid cells)
  r: number;
}

const ATTRACTORS: Attractor[] = [
  { phase: 0,    speed: 0.18, ax: 0.38, fx: 1.0, px: 0.0,  ay: 0.32, fy: 1.3, py: 0.4,  r: 10 },
  { phase: 1.8,  speed: 0.13, ax: 0.30, fx: 1.7, px: 1.1,  ay: 0.28, fy: 1.0, py: 2.3,  r: 8  },
  { phase: 3.4,  speed: 0.22, ax: 0.42, fx: 0.9, px: 0.7,  ay: 0.36, fy: 1.5, py: 0.9,  r: 9  },
  { phase: 5.1,  speed: 0.10, ax: 0.34, fx: 1.2, px: 3.1,  ay: 0.30, fy: 0.8, py: 1.6,  r: 11 },
];

// Pre-compute lookup: brightness [0..1] → RAMP index
function brightnessToChar(b: number): string {
  const idx = Math.min(Math.floor(b * RAMP.length), RAMP.length - 1);
  return RAMP[idx];
}

export function AsciiField() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const FONT_PX = 11;
    const CHAR_W = FONT_PX * 0.61; // JetBrains Mono is slightly condensed
    const CHAR_H = FONT_PX * 1.45;

    let cols = 0;
    let rows = 0;
    let field: Float32Array | null = null;
    let animId = 0;
    let lastFrame = 0;
    let t = 0;

    // Capture stable refs for use in closures
    const cv = canvas;
    const cx2 = ctx;

    function resize() {
      cv.width = window.innerWidth;
      cv.height = window.innerHeight;
      cols = Math.ceil(cv.width / CHAR_W);
      rows = Math.ceil(cv.height / CHAR_H);
      field = new Float32Array(cols * rows);
    }

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(document.documentElement);

    function computeField(t: number) {
      if (!field) return;
      field.fill(0);

      for (const a of ATTRACTORS) {
        const phase = a.phase + t * a.speed;
        // Attractor center in grid coords
        const cx = (0.5 + a.ax * Math.sin(a.fx * phase + a.px)) * cols;
        const cy = (0.5 + a.ay * Math.cos(a.fy * phase + a.py)) * rows;
        const r2 = a.r * a.r;

        // Bounding box to avoid full O(cols*rows) per attractor
        const x0 = Math.max(0, Math.floor(cx - a.r * 3));
        const x1 = Math.min(cols - 1, Math.ceil(cx + a.r * 3));
        const y0 = Math.max(0, Math.floor(cy - a.r * 3));
        const y1 = Math.min(rows - 1, Math.ceil(cy + a.r * 3));

        for (let y = y0; y <= y1; y++) {
          const dy = y - cy;
          const dy2 = dy * dy;
          for (let x = x0; x <= x1; x++) {
            const dx = x - cx;
            const dist2 = dx * dx + dy2;
            field[y * cols + x] += Math.exp(-dist2 / (2 * r2));
          }
        }
      }

      // Normalize so max ≈ 1
      let max = 0;
      for (let i = 0; i < field.length; i++) if (field[i] > max) max = field[i];
      if (max > 0) for (let i = 0; i < field.length; i++) field[i] /= max;
    }

    function draw(now: number) {
      animId = requestAnimationFrame(draw);

      // Throttle to ~12fps
      if (now - lastFrame < 82) return;
      lastFrame = now;
      t += 0.016;

      computeField(t);
      if (!field) return;

      cx2.clearRect(0, 0, cv.width, cv.height);
      cx2.font = `${FONT_PX}px "JetBrains Mono", ui-monospace, monospace`;

      const isLight = document.documentElement.getAttribute("data-theme") === "light";
      // Dark: lavender-tinted glow. Light: deep indigo.
      cx2.fillStyle = isLight ? "rgba(50, 30, 140, 0.22)" : "rgba(195, 192, 255, 0.13)";

      for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols; x++) {
          const b = field[y * cols + x];
          if (b < 0.08) continue; // skip near-empty
          const ch = brightnessToChar(b);
          if (ch === " ") continue;
          cx2.fillText(ch, x * CHAR_W, y * CHAR_H + FONT_PX);
        }
      }
    }

    animId = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(animId);
      ro.disconnect();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0"
      style={{ zIndex: 1 }}
      aria-hidden
    />
  );
}
