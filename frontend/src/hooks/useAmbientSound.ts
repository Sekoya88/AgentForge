"use client";

import { useCallback, useEffect, useRef } from "react";

const STORAGE_KEY = "agentforge_ambient_sound";

/** Returns the current preference from localStorage (default: true). */
export function getAmbientSoundEnabled(): boolean {
  if (typeof window === "undefined") return false;
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw === null ? true : raw === "true";
}

/** Persists the preference to localStorage. */
export function setAmbientSoundEnabled(value: boolean): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, String(value));
}

/**
 * Synthesizes a short 3-note ascending arpeggio (C5 → E5 → G5) using the
 * Web Audio API. No audio files required.
 *
 * Returns a `playChime` function. When called it checks the stored preference
 * and plays only if the user has opted in (default: true).
 */
export function useAmbientSound() {
  const ctxRef = useRef<AudioContext | null>(null);

  // Lazily create (or resume) the AudioContext on first use.
  const getCtx = useCallback((): AudioContext | null => {
    if (typeof window === "undefined") return null;
    if (!ctxRef.current) {
      ctxRef.current = new AudioContext();
    }
    if (ctxRef.current.state === "suspended") {
      void ctxRef.current.resume();
    }
    return ctxRef.current;
  }, []);

  // Close the AudioContext on unmount to avoid leaks.
  useEffect(() => {
    return () => {
      ctxRef.current?.close().catch(() => undefined);
      ctxRef.current = null;
    };
  }, []);

  /**
   * Plays a 3-note ascending arpeggio completion chime.
   * Silently no-ops if ambient sound is disabled or AudioContext unavailable.
   */
  const playChime = useCallback(() => {
    if (!getAmbientSoundEnabled()) return;
    const ctx = getCtx();
    if (!ctx) return;

    const notes: { freq: number; duration: number; startOffset: number }[] = [
      { freq: 523, duration: 0.08, startOffset: 0 },      // C5
      { freq: 659, duration: 0.08, startOffset: 0.09 },   // E5
      { freq: 784, duration: 0.12, startOffset: 0.18 },   // G5
    ];

    const masterGain = ctx.createGain();
    masterGain.gain.setValueAtTime(0.28, ctx.currentTime);
    masterGain.connect(ctx.destination);

    notes.forEach(({ freq, duration, startOffset }) => {
      const osc = ctx.createOscillator();
      const env = ctx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, ctx.currentTime + startOffset);

      const t0 = ctx.currentTime + startOffset;
      // Fast fade-in (5 ms), slow fade-out over the note duration.
      env.gain.setValueAtTime(0, t0);
      env.gain.linearRampToValueAtTime(1, t0 + 0.005);
      env.gain.exponentialRampToValueAtTime(0.001, t0 + duration);

      osc.connect(env);
      env.connect(masterGain);

      osc.start(t0);
      osc.stop(t0 + duration + 0.01);

      // Clean up nodes after they finish.
      osc.onended = () => {
        osc.disconnect();
        env.disconnect();
      };
    });

    // Disconnect master after last note finishes.
    const totalDuration = 0.18 + 0.12 + 0.02;
    setTimeout(() => masterGain.disconnect(), (totalDuration + 0.05) * 1000);
  }, [getCtx]);

  return { playChime };
}
