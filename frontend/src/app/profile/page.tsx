"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";

type MeResponse = {
  id: string;
  email: string;
  display_name: string | null;
};

export default function ProfilePage() {
  const router = useRouter();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const u = await api<MeResponse>("/api/v1/auth/me");
        if (!c) setMe(u);
      } catch (e) {
        if (!c) {
          if (e instanceof ApiError && e.status === 401) {
            router.push("/login");
            return;
          }
          setLoadError(e instanceof Error ? e.message : "Failed to load profile");
        }
      }
    })();
    return () => {
      c = true;
    };
  }, [router]);

  async function onChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setFormSuccess(null);
    if (newPassword.length < 8) {
      setFormError("New password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setFormError("New password and confirmation do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await api("/api/v1/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      setFormSuccess("Password updated.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmNewPassword("");
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Could not change password");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <ToolShell active="profile">
      <div className="mx-auto max-w-2xl">
        <span className="af-kicker mb-2 block text-af-primary">[ PROFILE ]</span>
        <h1 className="mb-8 font-sans text-3xl font-bold tracking-tight text-white md:text-4xl">
          Your <span className="af-serif-italic text-af-primary">account</span>
        </h1>

        {loadError && (
          <p className="mb-6 rounded-lg border border-af-error/30 bg-af-error/10 px-4 py-3 text-sm text-af-error">
            {loadError}
          </p>
        )}

        {!me && !loadError && <p className="text-af-muted">Loading...</p>}

        {me && (
          <div className="space-y-6">
            <section className="af-card p-6">
              <p className="mb-4 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                Identity
              </p>
              <dl className="space-y-3 text-sm">
                <div className="flex flex-col gap-1 border-b border-af-border/20 pb-3 sm:flex-row sm:justify-between">
                  <dt className="text-af-muted">Email</dt>
                  <dd className="font-mono text-white">{me.email}</dd>
                </div>
                <div className="flex flex-col gap-1 border-b border-af-border/20 pb-3 sm:flex-row sm:justify-between">
                  <dt className="text-af-muted">Display name</dt>
                  <dd className="font-mono text-white">{me.display_name ?? "—"}</dd>
                </div>
                <div className="flex flex-col gap-1 sm:flex-row sm:justify-between">
                  <dt className="text-af-muted">User ID</dt>
                  <dd className="break-all font-mono text-xs text-white">{me.id}</dd>
                </div>
              </dl>
            </section>

            <section className="af-card p-6">
              <p className="mb-4 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                Change password
              </p>
              <form onSubmit={onChangePassword} className="space-y-4">
                <div className="space-y-2">
                  <label
                    htmlFor="current_password"
                    className="ml-1 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim"
                  >
                    Current password
                  </label>
                  <input
                    id="current_password"
                    type="password"
                    required
                    autoComplete="current-password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="af-input w-full py-2.5 font-mono"
                  />
                </div>
                <div className="space-y-2">
                  <label
                    htmlFor="new_password"
                    className="ml-1 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim"
                  >
                    New password
                  </label>
                  <input
                    id="new_password"
                    type="password"
                    required
                    minLength={8}
                    autoComplete="new-password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="af-input w-full py-2.5 font-mono"
                  />
                  <p className="text-xs text-af-muted">Minimum 8 characters.</p>
                </div>
                <div className="space-y-2">
                  <label
                    htmlFor="confirm_new_password"
                    className="ml-1 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim"
                  >
                    Confirm new password
                  </label>
                  <input
                    id="confirm_new_password"
                    type="password"
                    required
                    minLength={8}
                    autoComplete="new-password"
                    value={confirmNewPassword}
                    onChange={(e) => setConfirmNewPassword(e.target.value)}
                    className="af-input w-full py-2.5 font-mono"
                  />
                </div>
                {formError && (
                  <p className="rounded-lg border border-af-error/30 bg-af-error/10 px-3 py-2 text-sm text-af-error">
                    {formError}
                  </p>
                )}
                {formSuccess && (
                  <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400">
                    {formSuccess}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={submitting}
                  className="af-btn-primary w-full py-2.5 text-sm disabled:opacity-50"
                >
                  {submitting ? "Updating…" : "Update password"}
                </button>
              </form>
            </section>
          </div>
        )}
      </div>
    </ToolShell>
  );
}
