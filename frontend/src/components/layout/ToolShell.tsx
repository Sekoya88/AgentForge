"use client";

import Link from "next/link";

export type ToolSection = "agents" | "campaigns" | "skills" | "sandbox" | "finetune";

const SIDENAV: { href: string; label: string; icon: string; section: ToolSection }[] = [
  { href: "/agents", label: "Agents", icon: "smart_toy", section: "agents" },
  { href: "/sandbox", label: "Sandbox", icon: "biotech", section: "sandbox" },
  { href: "/campaigns", label: "Campaigns", icon: "rocket_launch", section: "campaigns" },
  { href: "/skills", label: "Skills", icon: "psychology", section: "skills" },
  { href: "/finetune", label: "Finetune", icon: "tune", section: "finetune" },
];

export function ToolShell({
  active,
  children,
}: {
  active: ToolSection;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-[calc(100vh-4rem)]">
      <aside className="sticky top-16 hidden h-[calc(100vh-4rem)] w-64 flex-col border-r border-white/5 bg-slate-950/80 py-4 font-mono text-sm backdrop-blur-lg lg:flex">
        <div className="mb-8 px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded bg-af-indigo">
              <span
                className="material-symbols-outlined text-lg text-white"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                bolt
              </span>
            </div>
            <div>
              <p className="text-sm font-black leading-none text-indigo-400">AgentForge</p>
              <p className="mt-1 text-[10px] uppercase tracking-widest text-slate-500">v0.1.0</p>
            </div>
          </div>
        </div>
        <nav className="flex-1 space-y-1">
          {SIDENAV.map((item) => {
            const highlighted = item.section === active;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={
                  highlighted
                    ? "flex items-center gap-3 border-r-2 border-indigo-500 bg-indigo-500/10 px-6 py-3 font-bold text-indigo-400 transition-all"
                    : "flex items-center gap-3 px-6 py-3 text-slate-500 transition-all hover:bg-white/5 hover:text-slate-300"
                }
              >
                <span className="material-symbols-outlined">{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="px-4 pb-4">
          <Link
            href="/agents/new"
            className="mb-4 block w-full rounded-lg bg-white py-2 text-center text-xs font-bold text-af-surface-dim transition-all hover:shadow-[0_0_12px_rgba(79,70,229,0.3)]"
          >
            + New Agent
          </Link>
          <Link
            href="/"
            className="flex items-center gap-3 px-2 py-2 text-xs text-slate-500 hover:text-slate-300"
          >
            <span className="material-symbols-outlined text-sm">home</span>
            Home
          </Link>
        </div>
      </aside>
      <div className="relative z-10 flex-1 overflow-x-hidden px-4 py-8 md:px-8 lg:px-12">
        {children}
      </div>
    </div>
  );
}
