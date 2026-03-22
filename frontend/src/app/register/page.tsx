"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
          display_name: displayName || null,
        }),
      });
      router.push("/login");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Register failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative z-10 mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-md flex-col justify-center px-6 py-12">
      <header className="mb-10 text-center">
        <div className="mb-8 flex justify-center">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-3xl text-af-primary">person_add</span>
            <span className="text-xl font-bold tracking-tighter text-af-on-surface">AgentForge</span>
          </div>
        </div>
        <span className="af-kicker">[ CREATE ACCOUNT ]</span>
        <h1 className="mt-2 font-mono text-4xl tracking-tight text-af-on-surface">
          Join the <span className="af-serif-italic text-af-primary">forge</span>
        </h1>
      </header>
      <div className="rounded-xl border border-af-border bg-af-surface-low p-8 shadow-2xl backdrop-blur-sm">
        <form onSubmit={onSubmit} className="space-y-5">
          <div className="space-y-2">
            <label className="ml-1 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Display name
            </label>
            <input
              type="text"
              id="display_name"
              autoComplete="name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="af-input font-mono"
            />
          </div>
          <div className="space-y-2">
            <label className="ml-1 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim" htmlFor="email">
              Email
            </label>
            <input
              type="email"
              id="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="af-input font-mono"
            />
          </div>
          <div className="space-y-2">
            <label className="ml-1 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim" htmlFor="password">
              Password (min 8)
            </label>
            <input
              type="password"
              id="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="af-input font-mono"
            />
          </div>
          {error && <p className="text-sm text-af-error">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-af-inverse py-3.5 font-bold text-af-surface-dim transition-all hover:shadow-[0_0_20px_rgba(195,192,255,0.3)] active:scale-[0.98] disabled:opacity-50"
          >
            {loading ? "…" : "Create account"}
          </button>
        </form>
      </div>
      <p className="mt-8 text-center font-mono text-xs text-af-muted-dim">
        Already have access?{" "}
        <Link href="/login" className="font-bold text-af-primary hover:text-white">
          Sign in
        </Link>
      </p>
    </main>
  );
}
