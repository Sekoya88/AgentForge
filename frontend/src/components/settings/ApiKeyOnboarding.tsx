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
    description:
      "Powers Claude models (claude-sonnet-4-6, claude-opus-4-7). Required for the Forge assistant default mode.",
    getKeyUrl: "https://console.anthropic.com/settings/keys",
    keyFormat: "sk-ant-api03-…",
    required: true,
  },
  {
    id: "openai",
    name: "OpenAI",
    field: "openai_key",
    description: "Powers GPT-4o and o3 models. Required for OpenAI-based agents and fine-tuning.",
    getKeyUrl: "https://platform.openai.com/api-keys",
    keyFormat: "sk-proj-…",
    required: true,
  },
  {
    id: "google",
    name: "Google (Gemini)",
    field: "google_key",
    description: "Powers Gemini 2.5 Pro. Required for Google provider agents.",
    getKeyUrl: "https://aistudio.google.com/app/apikey",
    keyFormat: "AIza…",
    required: false,
  },
  {
    id: "tavily",
    name: "Tavily",
    field: "tavily_key",
    description: "Enables the Forge assistant web search tool and agent web retrieval.",
    getKeyUrl: "https://app.tavily.com/",
    keyFormat: "tvly-…",
    required: false,
  },
  {
    id: "hf",
    name: "HuggingFace",
    field: "hf_token",
    description:
      "Required for browsing HuggingFace models from Forge and for fine-tuning jobs.",
    getKeyUrl: "https://huggingface.co/settings/tokens",
    keyFormat: "hf_…",
    required: false,
  },
  {
    id: "elevenlabs",
    name: "ElevenLabs",
    field: "elevenlabs_key",
    description: "Powers voice synthesis in voice-assistant agents.",
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
  const [activeTab, setActiveTab] = useState(0);
  const [keyValues, setKeyValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [saved, setSaved] = useState<Record<string, boolean>>({});

  const provider = PROVIDERS[activeTab];

  async function handleSave(field: string) {
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

  const allRequiredSet = PROVIDERS.filter((p) => p.required).every(
    (p) => existingKeys[`has_${p.id}_key`] || saved[p.field]
  );

  function isProviderSet(p: Provider): boolean {
    return !!(existingKeys[`has_${p.id}_key`] || saved[p.field]);
  }

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
          {allRequiredSet && (
            <button onClick={onDismiss} className="af-btn-primary px-4 py-2 text-sm">
              Done ✓
            </button>
          )}
        </div>

        <div className="flex gap-1 mt-4 flex-wrap">
          {PROVIDERS.map((p, i) => {
            const isSet = isProviderSet(p);
            return (
              <button
                key={p.id}
                onClick={() => setActiveTab(i)}
                className="px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5 border"
                style={{
                  borderColor: activeTab === i ? "var(--af-accent)" : "var(--af-border)",
                  background:
                    activeTab === i
                      ? "color-mix(in srgb, var(--af-accent) 15%, transparent)"
                      : "transparent",
                  color: activeTab === i ? "var(--af-accent)" : "var(--af-text-muted)",
                }}
              >
                {isSet && <span style={{ color: "#4ade80" }}>✓</span>}
                {p.name}
                {p.required && !isSet && (
                  <span style={{ color: "#fb923c", fontSize: "10px" }}>required</span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      <div className="px-6 py-5 flex flex-col gap-4">
        <p className="text-sm af-text-secondary">{provider.description}</p>

        <div className="flex items-center gap-2 text-sm">
          <span className="af-text-muted">Get your key →</span>
          <a
            href={provider.getKeyUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium hover:underline"
            style={{ color: "var(--af-accent)" }}
          >
            {provider.getKeyUrl.replace("https://", "")}
          </a>
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-xs af-text-muted uppercase tracking-wider">{provider.name} Key</label>
          <div className="flex gap-2">
            <input
              type="password"
              placeholder={provider.keyFormat}
              value={keyValues[provider.field] ?? ""}
              onChange={(e) =>
                setKeyValues((prev) => ({ ...prev, [provider.field]: e.target.value }))
              }
              className="af-input flex-1 font-mono text-sm"
            />
            <button
              onClick={() => handleSave(provider.field)}
              disabled={!keyValues[provider.field]?.trim() || saving === provider.field}
              className="af-btn-primary px-4 py-2 text-sm disabled:opacity-40"
            >
              {saving === provider.field ? "Saving…" : "Save"}
            </button>
          </div>
          {isProviderSet(provider) && (
            <p className="text-xs flex items-center gap-1" style={{ color: "#4ade80" }}>
              <span>✓</span> Key saved — encrypted at rest
            </p>
          )}
        </div>

        <div className="flex justify-between pt-2">
          <button
            onClick={() => setActiveTab((i) => Math.max(0, i - 1))}
            disabled={activeTab === 0}
            className="text-sm af-text-muted hover:af-text-primary disabled:opacity-30"
          >
            ← Previous
          </button>
          <button
            onClick={() => setActiveTab((i) => Math.min(PROVIDERS.length - 1, i + 1))}
            disabled={activeTab === PROVIDERS.length - 1}
            className="text-sm hover:underline disabled:opacity-30"
            style={{ color: "var(--af-accent)" }}
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}
