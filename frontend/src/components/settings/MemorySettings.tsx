"use client";

import { useState } from "react";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const HOURS = Array.from({ length: 24 }, (_, i) => ({
  value: i,
  label: `${String(i).padStart(2, "0")}:00 UTC`,
}));

interface Props {
  memoryEnabled: boolean;
  compactionDay: number;
  compactionHour: number;
  lastCompactedAt: string | null;
  nextRunAt: string | null;
  memoryCount: number;
  onSave: (enabled: boolean, day: number, hour: number) => Promise<void>;
}

export function MemorySettings({
  memoryEnabled,
  compactionDay,
  compactionHour,
  lastCompactedAt,
  nextRunAt,
  memoryCount,
  onSave,
}: Props) {
  const [enabled, setEnabled] = useState(memoryEnabled);
  const [day, setDay] = useState(compactionDay);
  const [hour, setHour] = useState(compactionHour);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    try {
      await onSave(enabled, day, hour);
      setSaved(true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="af-card p-6 flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-base font-semibold af-text-primary">Forge Long-term Memory</h3>
          <p className="text-sm af-text-muted mt-1">
            Forge compacts your past conversations weekly into searchable memories, so it learns your preferences over time.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setEnabled((v) => !v)}
          className="relative w-10 h-6 rounded-full transition-colors flex-shrink-0 mt-0.5"
          style={{ background: enabled ? "var(--af-accent)" : "var(--af-border)" }}
          aria-label="Toggle memory"
        >
          <span
            className="absolute top-1 w-4 h-4 rounded-full bg-white transition-transform"
            style={{ transform: enabled ? "translateX(18px)" : "translateX(2px)" }}
          />
        </button>
      </div>

      {enabled && (
        <>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs af-text-muted uppercase tracking-wider">Compact every</label>
              <select
                value={day}
                onChange={(e) => setDay(Number(e.target.value))}
                className="af-input text-sm"
              >
                {DAYS.map((d, i) => (
                  <option key={d} value={i}>{d}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs af-text-muted uppercase tracking-wider">At time (UTC)</label>
              <select
                value={hour}
                onChange={(e) => setHour(Number(e.target.value))}
                className="af-input text-sm"
              >
                {HOURS.map((h) => (
                  <option key={h.value} value={h.value}>{h.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex gap-6 text-sm">
            <div>
              <span className="af-text-muted">Memories stored: </span>
              <span className="af-text-primary font-medium">{memoryCount}</span>
            </div>
            {lastCompactedAt && (
              <div>
                <span className="af-text-muted">Last compacted: </span>
                <span className="af-text-primary font-medium">
                  {new Date(lastCompactedAt).toLocaleDateString()}
                </span>
              </div>
            )}
            {nextRunAt && (
              <div>
                <span className="af-text-muted">Next run: </span>
                <span className="af-text-primary font-medium">
                  {new Date(nextRunAt).toLocaleDateString()}
                </span>
              </div>
            )}
          </div>
        </>
      )}

      <div className="flex items-center justify-between pt-2 border-t" style={{ borderColor: "var(--af-border)" }}>
        {saved && (
          <span className="text-xs" style={{ color: "#4ade80" }}>✓ Saved</span>
        )}
        {!saved && <span />}
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="af-btn-primary px-5 py-2 text-sm disabled:opacity-40"
        >
          {saving ? "Saving…" : "Save memory settings"}
        </button>
      </div>
    </div>
  );
}
