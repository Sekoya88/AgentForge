"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { API_BASE, ApiError, api } from "@/lib/api";

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
  const [savingSecrets, setSavingSecrets] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [googleStatus, setGoogleStatus] = useState<GoogleIntegrationStatus | null>(null);
  const [googleStatusLoading, setGoogleStatusLoading] = useState(true);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [apiKeyLoading, setApiKeyLoading] = useState(false);
  const [apiKeyCopied, setApiKeyCopied] = useState(false);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const [s, sec] = await Promise.all([
          api<SystemSettings>("/api/v1/settings"),
          api<UserSecrets>("/api/v1/settings/secrets"),
        ]);
        if (!c) {
          setSettings(s);
          setSecrets(sec);
        }
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
        }),
      });
      setSecrets({
        has_openai_key: !!openaiKeyDraft || !!secrets?.has_openai_key,
        has_google_key: !!googleKeyDraft || !!secrets?.has_google_key,
        has_anthropic_key: !!anthropicKeyDraft || !!secrets?.has_anthropic_key,
        has_tavily_key: !!tavilyKeyDraft || !!secrets?.has_tavily_key,
      });
      setOpenaiKeyDraft("");
      setGoogleKeyDraft("");
      setAnthropicKeyDraft("");
      setTavilyKeyDraft("");
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
            <section className="af-card p-6">
              <p className="mb-4 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                User API Keys (Vault)
              </p>
              <p className="mb-4 text-xs text-af-muted">
                These keys are stored encrypted in the database and override the system defaults for your agents.
              </p>
              <form onSubmit={handleSaveSecrets} className="space-y-4">
                <div>
                  <label className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                    OpenAI API Key
                  </label>
                  <input
                    type="password"
                    value={openaiKeyDraft}
                    onChange={(e) => setOpenaiKeyDraft(e.target.value)}
                    placeholder={secrets?.has_openai_key ? "•••••••••••• (Saved)" : "sk-..."}
                    className="af-input w-full text-sm"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                    Google API Key
                  </label>
                  <input
                    type="password"
                    value={googleKeyDraft}
                    onChange={(e) => setGoogleKeyDraft(e.target.value)}
                    placeholder={secrets?.has_google_key ? "•••••••••••• (Saved)" : "AIza..."}
                    className="af-input w-full text-sm"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                    Anthropic API Key
                  </label>
                  <input
                    type="password"
                    value={anthropicKeyDraft}
                    onChange={(e) => setAnthropicKeyDraft(e.target.value)}
                    placeholder={secrets?.has_anthropic_key ? "•••••••••••• (Saved)" : "sk-ant-..."}
                    className="af-input w-full text-sm"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                    Tavily API Key
                  </label>
                  <input
                    type="password"
                    value={tavilyKeyDraft}
                    onChange={(e) => setTavilyKeyDraft(e.target.value)}
                    placeholder={secrets?.has_tavily_key ? "•••••••••••• (Saved)" : "tvly-..."}
                    className="af-input w-full text-sm"
                  />
                  <p className="mt-1 text-[11px] text-af-muted-dim">
                    Required for web search in Forge Assistant
                  </p>
                </div>
                <div className="flex items-center gap-4">
                  <button
                    type="submit"
                    disabled={savingSecrets}
                    className="af-btn-primary px-6 py-2 text-sm disabled:opacity-50"
                  >
                    {savingSecrets ? "Saving..." : "Save keys"}
                  </button>
                  {saveMsg && <span className="text-sm text-emerald-400">{saveMsg}</span>}
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
