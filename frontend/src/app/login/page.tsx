"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, setTokens } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api<{ access_token: string; refresh_token: string }>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setTokens(res.access_token, res.refresh_token);
      router.push("/agents");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative z-10 mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-md flex-col justify-center px-6 py-12">
      <header className="mb-10 text-center">
        <div className="mb-8 flex justify-center">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-3xl text-af-primary">token</span>
            <span className="text-xl font-bold tracking-tighter text-af-on-surface">AgentForge</span>
          </div>
        </div>
        <span className="af-kicker">[ SIGN IN ]</span>
        <h1 className="mt-2 font-mono text-4xl tracking-tight text-af-on-surface">
          Welcome <span className="af-serif-italic text-af-primary">back</span>
        </h1>
      </header>
      <div className="rounded-xl border border-af-border bg-af-surface-low p-8 shadow-2xl backdrop-blur-sm">
        <form onSubmit={onSubmit} className="space-y-6">
          <div className="space-y-2">
            <label htmlFor="email" className="ml-1 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Terminal ID
            </label>
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4">
                <span className="material-symbols-outlined text-lg text-af-muted-dim">alternate_email</span>
              </div>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.dev"
                className="af-input py-3 pl-11 font-mono"
              />
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-end justify-between px-1">
              <label htmlFor="password" className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                Access Key
              </label>
            </div>
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4">
                <span className="material-symbols-outlined text-lg text-af-muted-dim">lock</span>
              </div>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="af-input py-3 pl-11 font-mono"
              />
            </div>
          </div>
          {error && <p className="text-sm text-af-error">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="group flex w-full items-center justify-center gap-2 rounded-lg bg-af-inverse py-3.5 font-bold text-af-surface-dim transition-all duration-300 hover:bg-white hover:shadow-[0_0_20px_rgba(195,192,255,0.3)] active:scale-[0.98] disabled:opacity-50"
          >
            <span className="font-mono text-sm uppercase tracking-tighter">
              {loading ? "…" : "Initialize Session"}
            </span>
            <span className="material-symbols-outlined text-sm transition-transform group-hover:translate-x-1">
              arrow_forward
            </span>
          </button>
        </form>
      </div>
      <footer className="mt-10 space-y-4 text-center">
        <p className="font-mono text-xs text-af-muted-dim">
          New here?{" "}
          <Link
            href="/register"
            className="font-bold text-af-primary underline decoration-af-primary/30 underline-offset-4 transition-all hover:text-white"
          >
            Request Access
          </Link>
        </p>
      </footer>
    </main>
  );
}
