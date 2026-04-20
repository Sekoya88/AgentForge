"use client";

import { useState } from "react";

interface Provider {
  id: string;
  name: string;
  field: string;
  description: string;
  getKeyUrl: string;
  keyFormat: string;
  required: boolean;
}

const PROVIDERS: Provider[] = [
  {
    id: "anthropic",
    name: "Anthropic",
    field: "anthropic_key",
    description: "Powers Claude models. Required for Forge assistant.",
    getKeyUrl: "https://console.anthropic.com/settings/keys",
    keyFormat: "sk-ant-api03-…",
    required: true,
  },
  {
    id: "openai",
    name: "OpenAI",
    field: "openai_key",
    description: "Powers GPT-4o and o3. Required for OpenAI agents and fine-tuning.",
    getKeyUrl: "https://platform.openai.com/api-keys",
    keyFormat: "sk-proj-…",
    required: true,
  },
  {
    id: "google",
    name: "Google (Gemini)",
    field: "google_key",
    description: "Powers Gemini 2.5 Pro agents.",
    getKeyUrl: "https://aistudio.google.com/app/apikey",
    keyFormat: "AIza…",
    required: false,
  },
  {
    id: "tavily",
    name: "Tavily",
    field: "tavily_key",
    description: "Enables web search in Forge and agents.",
    getKeyUrl: "https://app.tavily.com/",
    keyFormat: "tvly-…",
    required: false,
  },
  {
    id: "hf",
    name: "HuggingFace",
    field: "hf_token",
    description: "For HF model browsing and fine-tuning jobs.",
    getKeyUrl: "https://huggingface.co/settings/tokens",
    keyFormat: "hf_…",
    required: false,
  },
  {
    id: "elevenlabs",
    name: "ElevenLabs",
    field: "elevenlabs_key",
    description: "Voice synthesis for voice-assistant agents.",
    getKeyUrl: "https://elevenlabs.io/app/settings/api-keys",
    keyFormat: "sk_…",
    required: false,
  },
];

interface Props {
  existingKeys: Record<string, boolean>;
  onSaveKey: (field: string, value: string) => Promise<void>;
  onDismiss: () => void;
}

export function ApiKeyOnboarding({ existingKeys, onSaveKey, onDismiss }: Props) {
  const [keyValues, setKeyValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [saved, setSaved] = useState<Record<string, boolean>>({});
  const [savingAll, setSavingAll] = useState(false);

  function isProviderSet(p: Provider): boolean {
    return !!(existingKeys[`has_${p.id}_key`] || saved[p.field]);
  }

  async function handleSaveOne(field: string) {
    const value = keyValues[field]?.trim();
    if (!value) return;
    setSaving(field);
    try {
      await onSaveKey(field, value);
      setSaved((prev) => ({ ...prev, [field]: true }));
      setKeyValues((prev) => ({ ...prev, [field]: "" }));
    } finally {
      setSaving(null);
    }
  }

  async function handleSaveAll() {
    const toSave = PROVIDERS.filter((p) => keyValues[p.field]?.trim());
    if (!toSave.length) return;
    setSavingAll(true);
    try {
      for (const p of toSave) {
        await onSaveKey(p.field, keyValues[p.field].trim());
        setSaved((prev) => ({ ...prev, [p.field]: true }));
        setKeyValues((prev) => ({ ...prev, [p.field]: "" }));
      }
    } finally {
      setSavingAll(false);
    }
  }

  const pendingCount = PROVIDERS.filter((p) => keyValues[p.field]?.trim()).length;
  const allRequiredSet = PROVIDERS.filter((p) => p.required).every((p) => isProviderSet(p));

  return (
    <div className="af-card p-0 overflow-hidden">
      <div className="px-6 pt-6 pb-4 border-b" style={{ borderColor: "var(--af-border)" }}>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold af-text-primary">Configure API Keys</h2>
            <p className="text-sm af-text-muted mt-1">
              Add your provider keys to unlock agents, Forge, and fine-tuning.
            </p>
          </div>
          <button type="button" onClick={onDismiss} className="text-sm af-text-muted hover:af-text-primary transition-colors">
            {allRequiredSet ? "Done ✓" : "Skip for now"}
          </button>
        </div>
      </div>

      <div className="px-6 py-4 flex flex-col gap-3 max-h-[60vh] overflow-y-auto">
        {PROVIDERS.map((p) => {
          const isSet = isProviderSet(p);
          const isSavingThis = saving === p.field;
          const hasInput = !!(keyValues[p.field]?.trim());

          return (
            <div
              key={p.id}
              className="flex flex-col gap-2 p-4 rounded-lg border"
              style={{ borderColor: isSet ? "color-mix(in srgb, #4ade80 30%, var(--af-border))" : "var(--af-border)" }}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold af-text-primary">{p.name}</span>
                  {p.required && !isSet && (
                    <span
                      className="text-xs px-1.5 py-0.5 rounded font-medium"
                      style={{ background: "color-mix(in srgb, #fb923c 15%, transparent)", color: "#fb923c" }}
                    >
                      required
                    </span>
                  )}
                  {isSet && (
                    <span className="text-xs flex items-center gap-1" style={{ color: "#4ade80" }}>
                      ✓ saved
                    </span>
                  )}
                </div>
                <a
                  href={p.getKeyUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs hover:underline"
                  style={{ color: "var(--af-accent)" }}
                >
                  Get key →
                </a>
              </div>

              <p className="text-xs af-text-muted">{p.description}</p>

              <div className="flex gap-2">
                <input
                  type="password"
                  placeholder={isSet ? "••••••••••••  (already set)" : p.keyFormat}
                  value={keyValues[p.field] ?? ""}
                  onChange={(e) => setKeyValues((prev) => ({ ...prev, [p.field]: e.target.value }))}
                  className="af-input flex-1 font-mono text-sm"
                />
                <button
                  type="button"
                  onClick={() => handleSaveOne(p.field)}
                  disabled={!hasInput || isSavingThis}
                  className="af-btn-primary px-3 py-1.5 text-xs disabled:opacity-40 whitespace-nowrap"
                >
                  {isSavingThis ? "…" : "Save"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {pendingCount > 0 && (
        <div className="px-6 py-4 border-t flex items-center justify-between" style={{ borderColor: "var(--af-border)" }}>
          <span className="text-sm af-text-muted">{pendingCount} key{pendingCount > 1 ? "s" : ""} ready to save</span>
          <button
            type="button"
            onClick={handleSaveAll}
            disabled={savingAll}
            className="af-btn-primary px-5 py-2 text-sm disabled:opacity-40"
          >
            {savingAll ? "Saving…" : `Save all (${pendingCount})`}
          </button>
        </div>
      )}
    </div>
  );
}
