"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/agents", label: "Agents", match: (p: string) => p.startsWith("/agents") },
  { href: "/sandbox", label: "Sandbox", match: (p: string) => p === "/sandbox" },
  { href: "/campaigns", label: "Campaigns", match: (p: string) => p.startsWith("/campaigns") },
  { href: "/skills", label: "Skills", match: (p: string) => p.startsWith("/skills") },
  { href: "/finetune", label: "Finetune", match: (p: string) => p.startsWith("/finetune") },
] as const;

export function AppHeader() {
  const pathname = usePathname();

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
      <div className="flex items-center gap-3">
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
      </div>
    </header>
  );
}
