"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { setTokens } from "@/lib/api";

/**
 * OAuth redirect target: backend sends tokens in the URL hash
 * (#access_token=...&refresh_token=...) or ?oauth_error=... on failure.
 */
export default function OAuthCallbackPage() {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const err = q.get("oauth_error");
    if (err) {
      setMessage(decodeURIComponent(err.replace(/\+/g, " ")));
      return;
    }
    const hash = window.location.hash.startsWith("#")
      ? window.location.hash.slice(1)
      : window.location.hash;
    const params = new URLSearchParams(hash);
    const access = params.get("access_token");
    const refresh = params.get("refresh_token");
    if (access && refresh) {
      setTokens(access, refresh);
      window.history.replaceState(null, "", window.location.pathname);
      router.replace("/agents");
      return;
    }
    setMessage("Missing tokens in callback URL.");
  }, [router]);

  if (message === null) {
    return (
      <main className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-md flex-col justify-center px-6 py-12">
        <p className="text-center font-mono text-sm text-af-muted-dim">Completing sign-in…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-md flex-col justify-center px-6 py-12">
      <h1 className="font-mono text-xl text-af-error">Sign-in failed</h1>
      <p className="mt-4 font-mono text-sm text-af-muted-dim">{message}</p>
      <Link
        href="/login"
        className="mt-8 inline-block font-mono text-sm font-bold text-af-primary hover:text-white"
      >
        Back to login
      </Link>
    </main>
  );
}
