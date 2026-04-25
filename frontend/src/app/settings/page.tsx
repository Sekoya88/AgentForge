"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { API_BASE, ApiError, api } from "@/lib/api";
import { ApiKeyOnboarding } from "@/components/settings/ApiKeyOnboarding";
import { MemorySettings } from "@/components/settings/MemorySettings";
import type { UserPreferences } from "@/lib/user-preferences";
import {
  getAmbientSoundEnabled,
  setAmbientSoundEnabled,
  useAmbientSound,
} from "@/hooks/useAmbientSound";

type SystemSettings = {
  sandbox_mode: string;
  redteam_mode: string;
  openai_configured: boolean;
  langfuse_configured: boolean;
  sentry_configured: boolean;
  cors_origins: string;
  database_url_redacted: string;
  redis_available: boolean;
};

type UserSecrets = {
  has_openai_key: boolean;
  has_google_key: boolean;
  has_anthropic_key: boolean;
  has_tavily_key: boolean;
  has_hf_token: boolean;
  has_elevenlabs_key: boolean;
};

type SsoConfig = {
  enabled: boolean;
  issuer: string | null;
};

type GoogleIntegrationStatus = {
  connected: boolean;
  scopes: string[];
  has_gmail_read: boolean;
  has_gmail_send: boolean;
  has_calendar_read: boolean;
  has_calendar_events: boolean;
};

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${ok ? "bg-emerald-400" : "bg-red-400"}`}
    />
  );
}

function SettingRow({
  label,
  value,
  ok,
}: {
  label: string;
  value: string;
  ok?: boolean;
}) {
  return (
    <div className="flex items-center justify-between border-b border-af-border/20 py-3 last:border-0">
      <span className="text-sm text-af-muted">{label}</span>
      <div className="flex items-center gap-2">
        {ok !== undefined && <StatusDot ok={ok} />}
        <span className="font-mono text-sm text-white">{value}</span>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const router = useRouter();
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [secrets, setSecrets] = useState<UserSecrets | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openaiKeyDraft, setOpenaiKeyDraft] = useState("");
  const [googleKeyDraft, setGoogleKeyDraft] = useState("");
  const [anthropicKeyDraft, setAnthropicKeyDraft] = useState("");
  const [tavilyKeyDraft, setTavilyKeyDraft] = useState("");
  const [hfTokenDraft, setHfTokenDraft] = useState("");
  const [elevenlabsKeyDraft, setElevenlabsKeyDraft] = useState("");
  const [savingSecrets, setSavingSecrets] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [ssoConfig, setSsoConfig] = useState<SsoConfig | null>(null);
  const [ssoLoading, setSsoLoading] = useState(true);
  const [googleStatus, setGoogleStatus] = useState<GoogleIntegrationStatus | null>(null);
  const [googleStatusLoading, setGoogleStatusLoading] = useState(true);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [apiKeyLoading, setApiKeyLoading] = useState(false);
  const [apiKeyCopied, setApiKeyCopied] = useState(false);
  const [prefs, setPrefs] = useState<UserPreferences | null>(null);
  const [memoryCount, setMemoryCount] = useState(0);
  const [ambientSound, setAmbientSound] = useState<boolean>(() => getAmbientSoundEnabled());
  const [showKeyOnboarding, setShowKeyOnboarding] = useState(false);
  const { playChime } = useAmbientSound();

  function handleAmbientSoundToggle() {
    const next = !ambientSound;
    setAmbientSound(next);
    setAmbientSoundEnabled(next);
    if (next) playChime();
  }

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const [s, sec, p] = await Promise.all([
          api<SystemSettings>("/api/v1/settings"),
          api<UserSecrets>("/api/v1/settings/secrets"),
          api<UserPreferences>("/api/v1/user-preferences"),
        ]);
        if (!c) {
          setSettings(s);
          setSecrets(sec);
          setPrefs(p);
          const hasRequired = sec.has_openai_key || sec.has_anthropic_key;
          if (!hasRequired) {
            setShowKeyOnboarding(true);
          }
        }
        try {
          const mc = await api<{ count: number }>("/api/v1/forge/memory/count");
          if (!c) setMemoryCount(mc.count);
        } catch {
          // non-critical
        }
        // SSO config — unauthenticated endpoint, fetch in parallel
        api<SsoConfig>("/api/v1/sso/config")
          .then((cfg) => { if (!c) { setSsoConfig(cfg); setSsoLoading(false); } })
          .catch(() => { if (!c) { setSsoConfig({ enabled: false, issuer: null }); setSsoLoading(false); } });

        try {
          const g = await api<GoogleIntegrationStatus>("/api/v1/auth/me/google-status");
          if (!c) {
            setGoogleStatus(g);
            setGoogleStatusLoading(false);
          }
        } catch {
          if (!c) {
            setGoogleStatus(null);
            setGoogleStatusLoading(false);
          }
        }
      } catch (e) {
        if (!c) {
          if (e instanceof ApiError && e.status === 401) {
            router.push("/login");
            return;
          }
          setError(e instanceof Error ? e.message : "Failed to load");
          setGoogleStatusLoading(false);
        }
      }
    })();
    return () => { c = true; };
  }, [router]);

  async function handleGenerateApiKey() {
    setApiKeyLoading(true);
    setApiKey(null);
    try {
      const data = await api<{ api_key: string }>("/api/v1/auth/me/token");
      setApiKey(data.api_key);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate API key");
    } finally {
      setApiKeyLoading(false);
    }
  }

  async function handleCopyApiKey() {
    if (!apiKey) return;
    await navigator.clipboard.writeText(apiKey);
    setApiKeyCopied(true);
    setTimeout(() => setApiKeyCopied(false), 2000);
  }

  async function handleSaveSecrets(e: React.FormEvent) {
    e.preventDefault();
    setSavingSecrets(true);
    setSaveMsg("");
    setError(null);
    try {
      await api("/api/v1/settings/secrets", {
        method: "PUT",
        body: JSON.stringify({
          openai_key: openaiKeyDraft || null,
          google_key: googleKeyDraft || null,
          anthropic_key: anthropicKeyDraft || null,
          tavily_key: tavilyKeyDraft || null,
          hf_token: hfTokenDraft || null,
          elevenlabs_key: elevenlabsKeyDraft || null,
        }),
      });
      setSecrets({
        has_openai_key: !!openaiKeyDraft || !!secrets?.has_openai_key,
        has_google_key: !!googleKeyDraft || !!secrets?.has_google_key,
        has_anthropic_key: !!anthropicKeyDraft || !!secrets?.has_anthropic_key,
        has_tavily_key: !!tavilyKeyDraft || !!secrets?.has_tavily_key,
        has_hf_token: !!hfTokenDraft || !!secrets?.has_hf_token,
        has_elevenlabs_key: !!elevenlabsKeyDraft || !!secrets?.has_elevenlabs_key,
      });
      setOpenaiKeyDraft("");
      setGoogleKeyDraft("");
      setAnthropicKeyDraft("");
      setTavilyKeyDraft("");
      setHfTokenDraft("");
      setElevenlabsKeyDraft("");
      setSaveMsg("Keys saved successfully.");
      setTimeout(() => setSaveMsg(""), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save keys");
    } finally {
      setSavingSecrets(false);
    }
  }

  return (
    <ToolShell active="settings">
      <div className="mx-auto max-w-2xl">
        <span className="af-kicker mb-2 block text-af-primary">[ SETTINGS ]</span>
        <h1 className="mb-8 font-sans text-3xl font-bold tracking-tight text-white md:text-4xl">
          System <span className="af-serif-italic text-af-primary">config</span>
        </h1>

        {error && (
          <p className="mb-6 rounded-lg border border-af-error/30 bg-af-error/10 px-4 py-3 text-sm text-af-error">
            {error}
          </p>
        )}

        {!settings && !error && <p className="text-af-muted">Loading...</p>}

        {settings && (
          <div className="space-y-6">
            {!showKeyOnboarding && !secrets?.has_anthropic_key && !secrets?.has_openai_key && (
              <div
                className="af-card p-4 flex items-center justify-between"
                style={{ borderColor: "rgba(249,115,22,0.4)", background: "rgba(249,115,22,0.05)" }}
              >
                <div>
                  <p className="text-sm font-medium af-text-primary">API keys not configured</p>
                  <p className="text-xs af-text-muted mt-0.5">
                    Add provider keys to enable agents, Forge, and fine-tuning.
                  </p>
                </div>
                <button
                  onClick={() => setShowKeyOnboarding(true)}
                  className="af-btn-primary px-4 py-2 text-sm"
                >
                  Set up keys
                </button>
              </div>
            )}

            {showKeyOnboarding && (
              <ApiKeyOnboarding
                existingKeys={secrets ?? {}}
                onSaveKey={async (field, value) => {
                  await api("/api/v1/settings/secrets", {
                    method: "PUT",
                    body: JSON.stringify({ [field]: value }),
                  });
                  setSecrets((prev) =>
                    prev ? { ...prev, [`has_${field}`]: true } as UserSecrets : prev
                  );
                }}
                onDismiss={() => setShowKeyOnboarding(false)}
              />
            )}

            <section className="af-card p-6">
              <p className="mb-4 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                User API Keys (Vault)
              </p>
              <p className="mb-4 text-xs text-af-muted">
                These keys are stored encrypted in the database and override the system defaults for your agents.
              </p>
              <form onSubmit={handleSaveSecrets} className="space-y-3">
                {/* ── OpenAI ── */}
                <div className="rounded-lg border border-af-border/30 bg-af-surface-container/30 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                      OpenAI API Key
                    </label>
                    <div className="flex items-center gap-1.5">
                      <StatusDot ok={!!secrets?.has_openai_key} />
                      <span className={`text-[10px] font-medium ${secrets?.has_openai_key ? "text-emerald-400" : "text-af-muted-dim"}`}>
                        {secrets?.has_openai_key ? "Saved" : "Not set"}
                      </span>
                    </div>
                  </div>
                  <input
                    type="password"
                    value={openaiKeyDraft}
                    onChange={(e) => setOpenaiKeyDraft(e.target.value)}
                    placeholder={secrets?.has_openai_key ? "Enter new key to replace…" : "sk-..."}
                    className="af-input w-full text-sm"
                  />
                  <p className="mt-1.5 text-[11px] text-af-muted-dim">
                    GPT models · Whisper ASR · OpenAI TTS · RAG embeddings · NL→agent generation
                  </p>
                </div>

                {/* ── Anthropic ── */}
                <div className="rounded-lg border border-af-border/30 bg-af-surface-container/30 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                      Anthropic API Key
                    </label>
                    <div className="flex items-center gap-1.5">
                      <StatusDot ok={!!secrets?.has_anthropic_key} />
                      <span className={`text-[10px] font-medium ${secrets?.has_anthropic_key ? "text-emerald-400" : "text-af-muted-dim"}`}>
                        {secrets?.has_anthropic_key ? "Saved" : "Not set"}
                      </span>
                    </div>
                  </div>
                  <input
                    type="password"
                    value={anthropicKeyDraft}
                    onChange={(e) => setAnthropicKeyDraft(e.target.value)}
                    placeholder={secrets?.has_anthropic_key ? "Enter new key to replace…" : "sk-ant-..."}
                    className="af-input w-full text-sm"
                  />
                  <p className="mt-1.5 text-[11px] text-af-muted-dim">
                    Claude models in Forge · Claude LLM nodes in agents
                  </p>
                </div>

                {/* ── Google ── */}
                <div className="rounded-lg border border-af-border/30 bg-af-surface-container/30 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                      Google API Key
                    </label>
                    <div className="flex items-center gap-1.5">
                      <StatusDot ok={!!secrets?.has_google_key} />
                      <span className={`text-[10px] font-medium ${secrets?.has_google_key ? "text-emerald-400" : "text-af-muted-dim"}`}>
                        {secrets?.has_google_key ? "Saved" : "Not set"}
                      </span>
                    </div>
                  </div>
                  <input
                    type="password"
                    value={googleKeyDraft}
                    onChange={(e) => setGoogleKeyDraft(e.target.value)}
                    placeholder={secrets?.has_google_key ? "Enter new key to replace…" : "AIza..."}
                    className="af-input w-full text-sm"
                  />
                  <p className="mt-1.5 text-[11px] text-af-muted-dim">
                    Gemini models in Forge · Gemini LLM nodes in agents
                  </p>
                </div>

                {/* ── ElevenLabs ── */}
                <div className="rounded-lg border border-af-border/30 bg-af-surface-container/30 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                      ElevenLabs API Key
                    </label>
                    <div className="flex items-center gap-1.5">
                      <StatusDot ok={!!secrets?.has_elevenlabs_key} />
                      <span className={`text-[10px] font-medium ${secrets?.has_elevenlabs_key ? "text-emerald-400" : "text-af-muted-dim"}`}>
                        {secrets?.has_elevenlabs_key ? "Saved" : "Not set"}
                      </span>
                    </div>
                  </div>
                  <input
                    type="password"
                    value={elevenlabsKeyDraft}
                    onChange={(e) => setElevenlabsKeyDraft(e.target.value)}
                    placeholder={secrets?.has_elevenlabs_key ? "Enter new key to replace…" : "xi_..."}
                    className="af-input w-full text-sm"
                  />
                  <div className="mt-2 rounded-md border border-af-primary/20 bg-af-primary/5 p-2.5">
                    <p className="mb-1 text-[10px] font-bold uppercase tracking-widest text-af-primary/60">
                      Voice Assistant — guide rapide
                    </p>
                    <ol className="space-y-0.5 text-[11px] text-af-muted-dim">
                      <li>1. Enregistre ta clé <span className="text-white/70">OpenAI</span> ci-dessus (Whisper ASR + GPT + TTS)</li>
                      <li>2. Enregistre ta clé <span className="text-white/70">ElevenLabs</span> ici pour des voix premium (optionnel)</li>
                      <li>3. Va sur <span className="font-mono text-af-primary/80">/agents/new</span> → Parcourir les templates → Voice Assistant</li>
                      <li>4. Dans la page de l&apos;agent, clique le bouton <span className="text-white/70">🎤 Voice mode</span> et parle</li>
                    </ol>
                  </div>
                </div>

                {/* ── Tavily ── */}
                <div className="rounded-lg border border-af-border/30 bg-af-surface-container/30 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                      Tavily API Key
                    </label>
                    <div className="flex items-center gap-1.5">
                      <StatusDot ok={!!secrets?.has_tavily_key} />
                      <span className={`text-[10px] font-medium ${secrets?.has_tavily_key ? "text-emerald-400" : "text-af-muted-dim"}`}>
                        {secrets?.has_tavily_key ? "Saved" : "Not set"}
                      </span>
                    </div>
                  </div>
                  <input
                    type="password"
                    value={tavilyKeyDraft}
                    onChange={(e) => setTavilyKeyDraft(e.target.value)}
                    placeholder={secrets?.has_tavily_key ? "Enter new key to replace…" : "tvly-..."}
                    className="af-input w-full text-sm"
                  />
                  <p className="mt-1.5 text-[11px] text-af-muted-dim">
                    Web search tool dans Forge Assistant
                  </p>
                </div>

                {/* ── HuggingFace ── */}
                <div className="rounded-lg border border-af-border/30 bg-af-surface-container/30 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                      HuggingFace Token
                    </label>
                    <div className="flex items-center gap-1.5">
                      <StatusDot ok={!!secrets?.has_hf_token} />
                      <span className={`text-[10px] font-medium ${secrets?.has_hf_token ? "text-emerald-400" : "text-af-muted-dim"}`}>
                        {secrets?.has_hf_token ? "Saved" : "Not set"}
                      </span>
                    </div>
                  </div>
                  <input
                    type="password"
                    value={hfTokenDraft}
                    onChange={(e) => setHfTokenDraft(e.target.value)}
                    placeholder={secrets?.has_hf_token ? "Enter new key to replace…" : "hf_..."}
                    className="af-input w-full text-sm"
                  />
                  <p className="mt-1.5 text-[11px] text-af-muted-dim">
                    Optionnel — recherche HuggingFace dans Forge · accès modèles privés
                  </p>
                </div>

                {/* ── Save button ── */}
                <div className="flex items-center gap-4 pt-1">
                  <button
                    type="submit"
                    disabled={savingSecrets}
                    className="af-btn-primary px-6 py-2 text-sm disabled:opacity-50"
                  >
                    {savingSecrets ? "Saving..." : "Save keys"}
                  </button>
                  {saveMsg && (
                    <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5">
                      <span className="h-2 w-2 rounded-full bg-emerald-400" />
                      <span className="text-sm text-emerald-400">{saveMsg}</span>
                    </div>
                  )}
                </div>
              </form>
            </section>

            <section className="af-card p-6">
              <p className="mb-4 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                SDK API Key
              </p>
              <p className="mb-4 text-xs text-af-muted">
                Generate a long-lived API key to use with the <code className="font-mono">agentforge-sdk</code> Python package.
              </p>
              <button
                onClick={handleGenerateApiKey}
                disabled={apiKeyLoading}
                className="af-btn-primary px-6 py-2 text-sm disabled:opacity-50"
              >
                {apiKeyLoading ? "Generating..." : "Generate API Key"}
              </button>
              {apiKey && (
                <div className="mt-4 space-y-2">
                  <div className="flex items-center gap-2 rounded-lg border border-af-border/30 bg-af-surface p-3">
                    <code className="flex-1 overflow-x-auto whitespace-nowrap font-mono text-xs text-af-primary">
                      {apiKey}
                    </code>
                    <button
                      onClick={handleCopyApiKey}
                      className="shrink-0 rounded border border-af-border/30 px-2 py-1 text-xs text-af-muted transition-colors hover:text-white"
                    >
                      {apiKeyCopied ? "Copied!" : "Copy"}
                    </button>
                  </div>
                  <p className="text-xs text-amber-400">
                    Store this securely — it will not be shown again after you navigate away.
                  </p>
                </div>
              )}
            </section>

            <section className="af-card p-6">
              <p className="mb-4 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                Google Workspace (OAuth)
              </p>
              <p className="mb-4 text-xs text-af-muted">
                Connect your Google account so agents can use Gmail and Calendar tools when those
                scopes are granted. Use reconnect after changing API configuration.
              </p>
              {googleStatusLoading ? (
                <p className="text-xs text-af-muted-dim">Loading Google status…</p>
              ) : googleStatus ? (
                <div className="space-y-3">
                  <SettingRow
                    label="Google account"
                    value={googleStatus.connected ? "Connected" : "Not connected"}
                    ok={googleStatus.connected}
                  />
                  {googleStatus.connected && (
                    <>
                      <SettingRow
                        label="Gmail (read)"
                        value={googleStatus.has_gmail_read ? "Granted" : "Not granted"}
                        ok={googleStatus.has_gmail_read}
                      />
                      <SettingRow
                        label="Gmail (send)"
                        value={googleStatus.has_gmail_send ? "Granted" : "Not granted"}
                        ok={googleStatus.has_gmail_send}
                      />
                      <SettingRow
                        label="Calendar (read)"
                        value={googleStatus.has_calendar_read ? "Granted" : "Not granted"}
                        ok={googleStatus.has_calendar_read}
                      />
                      <SettingRow
                        label="Calendar (events)"
                        value={googleStatus.has_calendar_events ? "Granted" : "Not granted"}
                        ok={googleStatus.has_calendar_events}
                      />
                    </>
                  )}
                  <a
                    href={`${API_BASE}/api/v1/auth/oauth/google`}
                    className="inline-flex rounded-lg border border-af-primary/40 bg-af-primary/10 px-4 py-2 text-sm font-bold text-af-primary transition-colors hover:bg-af-primary/20"
                  >
                    {googleStatus.connected ? "Reconnect Google" : "Connect Google"}
                  </a>
                </div>
              ) : (
                <p className="text-xs text-af-muted-dim">Could not load Google status.</p>
              )}
            </section>

            {/* ── SSO / OIDC ── */}
            <section className="af-card p-6">
              <p className="mb-4 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                SSO / OIDC (Enterprise)
              </p>
              <p className="mb-4 text-xs text-af-muted">
                Connect an enterprise identity provider (Okta, Auth0, Azure AD) so your team can sign
                in with their corporate credentials. Configure via environment variables.
              </p>

              {ssoLoading ? (
                <p className="text-xs text-af-muted-dim">Loading SSO status…</p>
              ) : ssoConfig?.enabled ? (
                <div className="space-y-3">
                  <SettingRow label="SSO enabled" value="Yes" ok={true} />
                  {ssoConfig.issuer && (
                    <SettingRow label="Issuer" value={ssoConfig.issuer} />
                  )}
                  <div className="pt-1">
                    <a
                      href="/api/v1/sso/login"
                      className="inline-flex rounded-lg border border-af-primary/40 bg-af-primary/10 px-4 py-2 text-sm font-bold text-af-primary transition-colors hover:bg-af-primary/20"
                    >
                      Sign in with SSO
                    </a>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <SettingRow label="SSO enabled" value="No" ok={false} />
                  <div className="rounded-lg border border-af-border/20 bg-af-surface-container/30 p-4">
                    <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                      How to enable
                    </p>
                    <ol className="space-y-1 text-[11px] text-af-muted-dim">
                      <li>1. Set <code className="font-mono text-white/60">SSO_OIDC_ISSUER</code> — your provider&apos;s issuer URL</li>
                      <li>2. Set <code className="font-mono text-white/60">SSO_OIDC_CLIENT_ID</code> and <code className="font-mono text-white/60">SSO_OIDC_CLIENT_SECRET</code></li>
                      <li>3. Set <code className="font-mono text-white/60">SSO_OIDC_REDIRECT_URI</code> to <code className="font-mono text-white/60">{"{backend}"}/api/v1/sso/callback</code></li>
                      <li>4. Restart the backend — the SSO login button will appear here</li>
                    </ol>
                    <p className="mt-3 text-[11px] text-amber-400/80">
                      Supported providers: Okta, Auth0, Azure AD, and any OIDC-compliant IdP.
                    </p>
                  </div>
                </div>
              )}
            </section>

            <section className="af-card p-6">
              <p className="mb-4 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                System Integrations
              </p>
              <SettingRow
                label="OpenAI API"
                value={settings.openai_configured ? "Connected" : "Not configured"}
                ok={settings.openai_configured}
              />
              <SettingRow
                label="Langfuse Tracing"
                value={settings.langfuse_configured ? "Connected" : "Disabled"}
                ok={settings.langfuse_configured}
              />
              <SettingRow
                label="Sentry Error Tracking"
                value={settings.sentry_configured ? "Connected" : "Disabled"}
                ok={settings.sentry_configured}
              />
            </section>

            <section className="af-card p-6">
              <p className="mb-4 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                Runtime
              </p>
              <SettingRow
                label="Sandbox Mode"
                value={settings.sandbox_mode}
                ok={true}
              />
              <SettingRow
                label="Red-team Engine"
                value={settings.redteam_mode}
                ok={true}
              />
              <SettingRow
                label="Redis"
                value={settings.redis_available ? "Connected" : "Unavailable"}
                ok={settings.redis_available}
              />
            </section>

            <section className="af-card p-6">
              <p className="mb-4 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                Infrastructure
              </p>
              <SettingRow
                label="Database"
                value={settings.database_url_redacted}
              />
              <SettingRow
                label="CORS Origins"
                value={settings.cors_origins || "—"}
              />
            </section>

            <section className="af-card p-6">
              <p className="mb-4 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                UI Preferences
              </p>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-af-on-surface">Ambient sound</p>
                  <p className="mt-0.5 text-xs text-af-muted">
                    Play a chime when an agent execution completes
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleAmbientSoundToggle}
                  aria-pressed={ambientSound}
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-af-primary focus-visible:ring-offset-2 ${
                    ambientSound ? "bg-af-primary" : "bg-af-surface-high"
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-md transition-transform duration-200 ${
                      ambientSound ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>
            </section>

            {prefs && (
              <MemorySettings
                memoryEnabled={prefs.memory_enabled}
                compactionDay={prefs.memory_compaction_day}
                compactionHour={prefs.memory_compaction_hour}
                lastCompactedAt={prefs.memory_last_compacted_at}
                nextRunAt={prefs.memory_next_run_at}
                memoryCount={memoryCount}
                onSave={async (enabled, day, hour) => {
                  await api("/api/v1/user-preferences", {
                    method: "PUT",
                    body: JSON.stringify({
                      memory_enabled: enabled,
                      memory_compaction_day: day,
                      memory_compaction_hour: hour,
                    }),
                  });
                }}
              />
            )}

            <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
              <p className="text-xs text-amber-400">
                These settings are read-only and configured via <code className="font-mono">.env</code>.
                Restart the backend after changes.
              </p>
            </div>
          </div>
        )}
      </div>
    </ToolShell>
  );
}
