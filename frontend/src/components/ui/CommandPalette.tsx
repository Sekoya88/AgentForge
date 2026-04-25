"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

// Static navigation commands
const NAV_COMMANDS = [
  { id: "go-dashboard", label: "Dashboard", icon: "home", href: "/dashboard", group: "Navigate" },
  { id: "go-agents", label: "Agents", icon: "smart_toy", href: "/agents", group: "Navigate" },
  { id: "go-forge", label: "Forge", icon: "bolt", href: "/forge", group: "Navigate" },
  { id: "go-knowledge", label: "Knowledge", icon: "book", href: "/knowledge", group: "Navigate" },
  { id: "go-campaigns", label: "Campaigns", icon: "security", href: "/campaigns", group: "Navigate" },
  { id: "go-executions", label: "Executions", icon: "play_circle", href: "/executions", group: "Navigate" },
  { id: "go-finetune", label: "Fine-tune", icon: "model_training", href: "/finetune", group: "Navigate" },
  { id: "go-settings", label: "Settings", icon: "settings", href: "/settings", group: "Navigate" },
];

// Static action commands
const ACTION_COMMANDS = [
  { id: "new-agent", label: "New Agent", icon: "add_circle", href: "/agents/new", group: "Actions" },
  { id: "open-forge", label: "Open Forge", icon: "bolt", href: "/forge", group: "Actions" },
];

type Command = {
  id: string;
  label: string;
  icon: string;
  href?: string;
  group: string;
  description?: string;
};

type AgentHit = { id: string; name: string; description?: string };

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [highlighted, setHighlighted] = useState(0);
  const [agentResults, setAgentResults] = useState<Command[]>([]);
  const [searching, setSearching] = useState(false);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setQuery("");
      setHighlighted(0);
      setAgentResults([]);
    }
  }, [open]);

  // Debounced agent search when query changes
  useEffect(() => {
    if (!open || !query.trim()) {
      setAgentResults([]);
      return;
    }
    setSearching(true);
    const t = setTimeout(async () => {
      try {
        const agents = await api<AgentHit[]>(`/api/v1/agents`);
        const q = query.toLowerCase();
        const hits = agents
          .filter((a) => a.name.toLowerCase().includes(q) || (a.description ?? "").toLowerCase().includes(q))
          .slice(0, 5)
          .map((a) => ({
            id: `agent-${a.id}`,
            label: a.name,
            icon: "smart_toy",
            href: `/agents/${a.id}`,
            group: "Agents",
            description: a.description ?? undefined,
          }));
        setAgentResults(hits);
      } catch { /* non-critical */ }
      setSearching(false);
    }, 220);
    return () => { clearTimeout(t); setSearching(false); };
  }, [query, open]);

  // Build filtered command list
  const q = query.toLowerCase();
  const staticCommands = [...NAV_COMMANDS, ...ACTION_COMMANDS].filter(
    (c) => !query || c.label.toLowerCase().includes(q) || c.group.toLowerCase().includes(q),
  );
  const allCommands = [...agentResults, ...staticCommands];

  // Group commands
  const groups: Record<string, Command[]> = {};
  for (const cmd of allCommands) {
    if (!groups[cmd.group]) groups[cmd.group] = [];
    groups[cmd.group].push(cmd);
  }

  const flatList = allCommands;

  // Reset highlighted when list changes
  useEffect(() => { setHighlighted(0); }, [query, agentResults.length]);

  // Execute a command
  function execute(cmd: Command) {
    if (cmd.href) router.push(cmd.href);
    onClose();
  }

  // Keyboard navigation
  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlighted((h) => Math.min(h + 1, flatList.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (flatList[highlighted]) execute(flatList[highlighted]);
    } else if (e.key === "Escape") {
      onClose();
    }
  }

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[200] bg-black/50 backdrop-blur-sm"
        onClick={onClose}
        style={{ animation: "af-fade-in 0.15s ease both" }}
      />
      {/* Palette */}
      <div
        className="fixed left-1/2 top-[15vh] z-[201] w-full max-w-xl -translate-x-1/2 overflow-hidden rounded-2xl border border-af-border bg-af-surface-container/95 shadow-[0_32px_80px_-12px_rgba(0,0,0,0.8)] backdrop-blur-xl"
        style={{ animation: "af-palette-in 0.18s cubic-bezier(0.22,1,0.36,1) both" }}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 border-b border-af-border/60 px-4 py-3.5">
          <span className="material-symbols-outlined text-xl text-af-muted-dim">
            {searching ? "progress_activity" : "search"}
          </span>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search agents, navigate pages, run actions…"
            className="flex-1 bg-transparent text-sm text-af-on-surface placeholder:text-af-muted-dim focus:outline-none"
          />
          <kbd className="rounded border border-af-border/60 px-1.5 py-0.5 text-[10px] text-af-muted-dim">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-[60vh] overflow-y-auto p-2">
          {flatList.length === 0 && !searching && (
            <p className="px-4 py-6 text-center text-sm text-af-muted-dim">
              No results for &ldquo;{query}&rdquo;
            </p>
          )}
          {Object.entries(groups).map(([group, cmds]) => (
            <div key={group} className="mb-1">
              <p className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                {group}
              </p>
              {cmds.map((cmd) => {
                const idx = flatList.indexOf(cmd);
                const isHl = idx === highlighted;
                return (
                  <button
                    key={cmd.id}
                    type="button"
                    onMouseEnter={() => setHighlighted(idx)}
                    onClick={() => execute(cmd)}
                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors ${
                      isHl ? "bg-af-primary/15 text-af-on-surface" : "text-af-muted hover:bg-white/5"
                    }`}
                  >
                    <span
                      className={`material-symbols-outlined text-lg ${isHl ? "text-af-primary" : "text-af-muted-dim"}`}
                    >
                      {cmd.icon}
                    </span>
                    <span className="flex-1">
                      <span className="block text-sm font-medium">{cmd.label}</span>
                      {cmd.description && (
                        <span className="block text-[11px] text-af-muted-dim">{cmd.description}</span>
                      )}
                    </span>
                    {isHl && (
                      <kbd className="rounded border border-af-primary/30 px-1.5 py-0.5 text-[10px] text-af-primary">
                        ↵
                      </kbd>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-4 border-t border-af-border/40 px-4 py-2 text-[10px] text-af-muted-dim">
          <span><kbd className="font-mono">↑↓</kbd> navigate</span>
          <span><kbd className="font-mono">↵</kbd> open</span>
          <span><kbd className="font-mono">Esc</kbd> close</span>
          <span className="ml-auto"><kbd className="font-mono">⌘K</kbd> to reopen</span>
        </div>
      </div>
    </>
  );
}
