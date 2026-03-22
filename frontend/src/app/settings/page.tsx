"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";

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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const s = await api<SystemSettings>("/api/v1/settings");
        if (!c) setSettings(s);
      } catch (e) {
        if (!c) {
          if (e instanceof ApiError && e.status === 401) {
            router.push("/login");
            return;
          }
          setError(e instanceof Error ? e.message : "Failed to load");
        }
      }
    })();
    return () => { c = true; };
  }, [router]);

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
                Integrations
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
