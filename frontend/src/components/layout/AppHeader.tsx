"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { clearTokens } from "@/lib/api";

const NAV = [
  { href: "/agents", label: "Agents", match: (p: string) => p.startsWith("/agents") },
  { href: "/sandbox", label: "Sandbox", match: (p: string) => p === "/sandbox" },
  { href: "/campaigns", label: "Campaigns", match: (p: string) => p.startsWith("/campaigns") },
  { href: "/skills", label: "Skills", match: (p: string) => p.startsWith("/skills") },
  { href: "/knowledge", label: "Knowledge", match: (p: string) => p.startsWith("/knowledge") },
  { href: "/finetune", label: "Finetune", match: (p: string) => p.startsWith("/finetune") },
] as const;

function readHasAccessToken(): boolean {
  if (typeof window === "undefined") return false;
  return Boolean(localStorage.getItem("access_token"));
}

export function AppHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const [authReady, setAuthReady] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(readHasAccessToken());
    setAuthReady(true);
  }, [pathname]);

  useEffect(() => {
    function syncFromStorage() {
      setLoggedIn(readHasAccessToken());
      setAuthReady(true);
    }
    function onStorage(e: StorageEvent) {
      if (e.key === "access_token" || e.key === null) syncFromStorage();
    }
    window.addEventListener("af-auth-changed", syncFromStorage);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener("af-auth-changed", syncFromStorage);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  function onLogout() {
    clearTokens();
    setLoggedIn(false);
    router.push("/");
  }

  return (
    <header className="af-glass-header fixed top-0 z-50 flex h-16 w-full items-center justify-between px-6 md:px-8">
      <Link
        href="/"
        className="font-mono text-lg font-bold tracking-tighter text-white"
      >
        AgentForge
      </Link>
      <nav className="hidden items-center gap-8 md:flex">
        {NAV.map(({ href, label, match }) => {
          const active = match(pathname);
          return (
            <Link
              key={href}
              href={href}
              className={
                active
                  ? "font-mono text-[13px] font-semibold tracking-tight text-white"
                  : "font-mono text-[13px] tracking-tight text-af-muted transition-colors hover:text-white"
              }
            >
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="flex min-h-[2.25rem] min-w-[8rem] items-center justify-end gap-3">
        {!authReady ? null : loggedIn ? (
          <button
            type="button"
            onClick={onLogout}
            className="font-mono text-[13px] text-af-muted transition-colors hover:text-white"
          >
            Sign out
          </button>
        ) : (
          <>
            <Link
              href="/login"
              className="font-mono text-[13px] text-af-muted transition-colors hover:text-white"
            >
              Login
            </Link>
            <Link
              href="/register"
              className="rounded-lg bg-af-inverse px-4 py-1.5 font-mono text-[13px] font-bold text-af-surface-dim transition-all hover:opacity-90 active:scale-95"
            >
              Get Started
            </Link>
          </>
        )}
      </div>
    </header>
  );
}
