"use client";

import Link from "next/link";

export type ToolSection =
  | "dashboard"
  | "walkthrough"
  | "agents"
  | "hub"
  | "forge"
  | "chat"
  | "campaigns"
  | "skills"
  | "sandbox"
  | "finetune"
  | "knowledge"
  | "executions"
  | "analytics"
  | "settings"
  | "profile";

const SIDENAV: { href: string; label: string; icon: string; section: ToolSection }[] = [
  { href: "/dashboard",  label: "Dashboard",   icon: "dashboard",      section: "dashboard" },
  { href: "/walkthrough",label: "Walkthrough",  icon: "map",            section: "walkthrough" },
  { href: "/agents",     label: "Agents",       icon: "smart_toy",      section: "agents" },
  { href: "/hub",        label: "Hub",          icon: "storefront",     section: "hub" },
  { href: "/forge",      label: "Forge",        icon: "bolt",           section: "forge" },
  { href: "/chat",       label: "Chat",         icon: "chat",           section: "chat" },
  { href: "/sandbox",    label: "Playground",   icon: "biotech",        section: "sandbox" },
  { href: "/campaigns",  label: "Campaigns",    icon: "rocket_launch",  section: "campaigns" },
  { href: "/skills",     label: "Skills",       icon: "psychology",     section: "skills" },
  { href: "/knowledge",  label: "Knowledge",    icon: "menu_book",      section: "knowledge" },
  { href: "/executions", label: "Executions",   icon: "history",        section: "executions" },
  { href: "/analytics",  label: "Analytics",    icon: "bar_chart",      section: "analytics" },
  { href: "/finetune",   label: "Finetune",     icon: "tune",           section: "finetune" },
  { href: "/settings",   label: "Settings",     icon: "settings",       section: "settings" },
  { href: "/profile",    label: "Profile",      icon: "person",         section: "profile" },
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
      <aside
        className="sticky top-16 hidden h-[calc(100vh-4rem)] w-64 flex-col py-4 font-mono text-sm lg:flex"
        style={{
          background: "var(--af-glass-medium)",
          backdropFilter: "blur(24px)",
          WebkitBackdropFilter: "blur(24px)",
          borderRight: "1px solid var(--af-glass-border)",
        }}
      >
        {/* Version badge */}
        <div className="mb-6 px-6">
          <span className="inline-block rounded-full border border-af-border/60 px-3 py-1 font-mono text-[10px] text-af-muted-dim">
            v0.1.0
          </span>
        </div>

        {/* Nav items */}
        <nav className="flex-1 space-y-0.5 overflow-y-auto pr-2 no-scrollbar">
          {SIDENAV.map((item) => {
            const active_ = item.section === active;
            return (
              <Link
                key={item.href}
                href={item.href}
                data-tour={item.section === "agents" ? "nav-agents" : undefined}
                className={`group relative flex items-center gap-3 rounded-r-lg px-6 py-2.5 font-sans transition-all duration-200 ${
                  active_
                    ? "bg-af-primary/10 text-af-primary font-bold"
                    : "text-af-muted hover:bg-white/5 hover:text-af-on-surface"
                }`}
              >
                {/* Active neon indicator */}
                {active_ && (
                  <span
                    className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 rounded-full bg-af-primary"
                    style={{ boxShadow: "0 0 8px rgba(195,192,255,0.6), 0 0 20px rgba(195,192,255,0.2)" }}
                  />
                )}
                {/* Hover reveal from left */}
                {!active_ && (
                  <span className="pointer-events-none absolute inset-0 rounded-r-lg bg-gradient-to-r from-af-primary/5 to-transparent opacity-0 transition-opacity duration-200 group-hover:opacity-100" />
                )}
                <span
                  className={`material-symbols-outlined text-[20px] transition-all ${
                    active_ ? "text-af-primary" : "text-af-muted-dim group-hover:text-af-muted"
                  }`}
                  style={active_ ? { filter: "drop-shadow(0 0 6px rgba(195,192,255,0.4))" } : undefined}
                >
                  {item.icon}
                </span>
                <span className="relative">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Bottom actions */}
        <div className="px-4 pb-2 pt-4 border-t border-af-border/40">
          <Link
            href="/agents/new"
            className="af-glow-pulse mb-3 block w-full rounded-lg bg-white py-2 text-center text-xs font-bold text-af-surface-dim transition-all hover:shadow-[0_0_20px_rgba(195,192,255,0.3)]"
          >
            + New Agent
          </Link>
          <Link
            href="/"
            className="flex items-center gap-3 rounded-lg px-2 py-2 text-xs text-af-muted transition-all hover:bg-white/5 hover:text-af-on-surface"
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
