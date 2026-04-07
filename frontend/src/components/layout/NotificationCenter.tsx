"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { NotificationItem, loadNotifications, markAllRead, saveNotifications, unreadCount } from "@/lib/notifications";

type ExecItem = { id: string; status: string; agent_name?: string; created_at?: string };

function typeIcon(type: NotificationItem["type"]): string {
  if (type === "execution_completed") return "check_circle";
  if (type === "execution_failed") return "error";
  if (type === "campaign_completed") return "security";
  return "model_training";
}

function typeColor(type: NotificationItem["type"]): string {
  if (type === "execution_completed") return "#34d399";
  if (type === "execution_failed") return "#f87171";
  if (type === "campaign_completed") return "#c084fc";
  return "#38bdf8";
}

function timeAgo(ms: number): string {
  const d = Math.floor((Date.now() - ms) / 1000);
  if (d < 60) return "just now";
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  return `${Math.floor(d / 86400)}d ago`;
}

export function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const panelRef = useRef<HTMLDivElement>(null);
  const knownIds = useRef<Set<string>>(new Set());

  // Load from localStorage on mount
  useEffect(() => {
    const stored = loadNotifications();
    setItems(stored);
    stored.forEach((n) => knownIds.current.add(n.id));
  }, []);

  // Poll for new notifications every 30 seconds
  const poll = useCallback(async () => {
    try {
      const newItems: NotificationItem[] = [];

      // Check recent executions
      const execs = await api<{ items: ExecItem[] }>("/api/v1/executions?limit=10").catch(() => ({ items: [] }));
      for (const ex of (execs.items ?? [])) {
        const nid = `exec_${ex.id}`;
        if (knownIds.current.has(nid)) continue;
        if (ex.status === "completed" || ex.status === "failed") {
          knownIds.current.add(nid);
          newItems.push({
            id: nid,
            type: ex.status === "completed" ? "execution_completed" : "execution_failed",
            title: ex.status === "completed" ? "Execution completed" : "Execution failed",
            message: ex.agent_name ?? ex.id,
            href: `/executions`,
            timestamp: ex.created_at ? new Date(ex.created_at).getTime() : Date.now(),
            read: false,
          });
        }
      }

      if (newItems.length > 0) {
        setItems((prev) => {
          const merged = [...newItems, ...prev].slice(0, 50);
          saveNotifications(merged);
          return merged;
        });
      }
    } catch { /* non-critical */ }
  }, []);

  useEffect(() => {
    poll();
    const interval = setInterval(poll, 30_000);
    return () => clearInterval(interval);
  }, [poll]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (!panelRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  function handleOpen() {
    setOpen((v) => !v);
  }

  function handleMarkAllRead() {
    setItems((prev) => {
      const updated = markAllRead(prev);
      saveNotifications(updated);
      return updated;
    });
  }

  const count = unreadCount(items);

  return (
    <div className="relative" ref={panelRef}>
      {/* Bell button */}
      <button
        type="button"
        onClick={handleOpen}
        className="relative flex h-8 w-8 items-center justify-center rounded-lg border border-af-border/60 text-af-muted transition-colors hover:border-af-primary/40 hover:text-af-primary"
        title="Notifications"
        aria-label={`Notifications (${count} unread)`}
      >
        <span className="material-symbols-outlined text-lg">notifications</span>
        {count > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-af-error px-1 text-[9px] font-bold text-white">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div
          className="absolute right-0 top-10 z-[150] w-80 overflow-hidden rounded-xl border border-af-border bg-af-surface-container/95 shadow-[0_16px_48px_-8px_rgba(0,0,0,0.6)] backdrop-blur-xl"
          style={{ animation: "af-fade-in 0.2s ease both" }}
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-af-border/60 px-4 py-3">
            <span className="text-[11px] font-bold uppercase tracking-widest text-af-muted-dim">
              Notifications
            </span>
            {count > 0 && (
              <button
                type="button"
                onClick={handleMarkAllRead}
                className="text-[11px] text-af-muted-dim hover:text-af-primary"
              >
                Mark all read
              </button>
            )}
          </div>

          {/* List */}
          <div className="max-h-80 overflow-y-auto">
            {items.length === 0 && (
              <div className="flex flex-col items-center gap-2 py-10 text-center">
                <span className="material-symbols-outlined text-3xl text-af-muted-dim">notifications_off</span>
                <p className="text-xs text-af-muted-dim">No notifications yet</p>
              </div>
            )}
            {items.map((n) => (
              <div
                key={n.id}
                className={`flex items-start gap-3 border-b border-af-border/30 px-4 py-3 transition-colors hover:bg-white/[0.02] ${
                  !n.read ? "bg-af-primary/5" : ""
                }`}
              >
                <span
                  className="material-symbols-outlined mt-0.5 text-lg"
                  style={{ color: typeColor(n.type) }}
                >
                  {typeIcon(n.type)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold text-af-on-surface">{n.title}</p>
                  <p className="truncate text-[11px] text-af-muted">{n.message}</p>
                  <p className="mt-0.5 text-[10px] text-af-muted-dim">{timeAgo(n.timestamp)}</p>
                </div>
                {n.href && (
                  <Link
                    href={n.href}
                    onClick={() => setOpen(false)}
                    className="shrink-0 text-[10px] text-af-muted-dim hover:text-af-primary"
                  >
                    View →
                  </Link>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
