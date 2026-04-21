"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import {
  ApiError,
  ForgeConversation,
  api,
  forgeCreateConversation,
  forgeDeleteConversation,
  forgeExecute,
  forgeGetMessages,
  forgeListConversations,
} from "@/lib/api";
import { consumeForgeSse } from "@/lib/sse";
import type { ChatMessage, AgentStep } from "@/types/chat";
import { getPreferences, updatePreferences } from "@/lib/user-preferences";
import { PersonalizationOnboarding } from "@/components/forge/PersonalizationOnboarding";
import { MarkdownMessage } from "@/components/chat/MarkdownMessage";
import { useAgentActivity } from "@/hooks/useAgentActivity";
import { AgentToastStack } from "@/components/agent/AgentToastStack";
import { AgentStepChips } from "@/components/agent/AgentStepChips";
import { InterruptPopup } from "@/components/execution/InterruptPopup";
import { WaveformIcon } from "@/components/agent/AgentActivityIcon";
import { useStreamingGap } from "@/hooks/useStreamingGap";

// ── Slash commands ────────────────────────────────────────────────────────────

type SlashCommand = {
  command: string;
  description: string;
  message: string;
  icon: string;
};

const SLASH_COMMANDS: SlashCommand[] = [
  {
    command: "/help",
    description: "Show all capabilities and commands",
    message: "/help — What can you do? List all your tools and how to use them in AgentForge.",
    icon: "help",
  },
  {
    command: "/voice",
    description: "Guide: set up Voice Assistant (ASR → LLM → TTS)",
    message: "/voice — Give me a step-by-step guide to set up my first Voice Assistant agent in AgentForge. I want to speak and hear the AI respond.",
    icon: "mic",
  },
  {
    command: "/agents",
    description: "List my agents",
    message: "/agents — List all my agents with their status.",
    icon: "smart_toy",
  },
  {
    command: "/create agent",
    description: "Help me design a new agent",
    message: "/create agent — Help me design a new agent. Ask me what it should do and suggest a graph structure.",
    icon: "add_circle",
  },
  {
    command: "/create skill",
    description: "Help me write a new skill",
    message: "/create skill — Help me write a new Python skill for my agents. Ask me what it should do.",
    icon: "code",
  },
  {
    command: "/finetune",
    description: "Guide: fine-tune a model on GPU",
    message: "/finetune — Explain how to launch a fine-tuning job in AgentForge using Modal GPU. What do I need to prepare?",
    icon: "model_training",
  },
  {
    command: "/redteam",
    description: "Guide: run a security campaign",
    message: "/redteam — How do I run a red-team security campaign on my agent? What are the 12 attack categories?",
    icon: "security",
  },
  {
    command: "/sdk",
    description: "Show Python & TypeScript SDK examples",
    message: "/sdk — Show me code examples for using the AgentForge Python SDK and TypeScript SDK to execute agents programmatically.",
    icon: "terminal",
  },
  {
    command: "/search",
    description: "Search the web (requires Tavily key)",
    message: "/search — Search the web for: ",
    icon: "search",
  },
  {
    command: "/python",
    description: "Run Python code in the sandbox REPL",
    message: "/python — Run this Python code in the sandbox: ",
    icon: "data_object",
  },
];

// ── Provider / model catalogue ────────────────────────────────────────────────

type ProviderOption = {
  id: string;
  label: string;
  models: { id: string; label: string }[];
};

const PROVIDERS: ProviderOption[] = [
  {
    id: "anthropic",
    label: "Anthropic",
    models: [
      { id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
      { id: "claude-opus-4-6", label: "Claude Opus 4.6" },
      { id: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" },
    ],
  },
  {
    id: "openai",
    label: "OpenAI",
    models: [
      { id: "gpt-5.4-mini", label: "GPT 5.4 Mini" },
      { id: "gpt-4o", label: "GPT-4o" },
      { id: "gpt-4o-mini", label: "GPT-4o Mini" },
    ],
  },
  {
    id: "gemini",
    label: "Google AI",
    models: [
      { id: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
      { id: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
      { id: "gemini-2.0-flash-lite", label: "Gemini 2.0 Flash Lite" },
      { id: "gemini-1.5-pro-latest", label: "Gemini 1.5 Pro" },
    ],
  },
];

const DEFAULT_PROVIDER = "anthropic";
const DEFAULT_MODEL = "claude-sonnet-4-6";

// ── Per-tab state ─────────────────────────────────────────────────────────────

type TabState = {
  convId: string;
  messages: ChatMessage[];
  provider: string;
  model: string;
  draft: string;
  loading: boolean;
  error: string | null;
};

function makeTab(convId: string, provider: string, model: string): TabState {
  return { convId, messages: [], provider, model, draft: "", loading: false, error: null };
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function relativeDate(iso: string | null): string {
  if (!iso) return "";
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 172800) return "yesterday";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function timeAgo(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 5) return "now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function providerIcon(provider: string): string {
  if (provider === "anthropic") return "android";
  if (provider === "openai") return "auto_awesome";
  if (provider === "gemini") return "stars";
  return "smart_toy";
}

// ── Streaming cursor indicator ────────────────────────────────────────────────

function StreamingCursor({ isStreaming, lastTokenAt }: { isStreaming: boolean; lastTokenAt?: number }) {
  const showGap = useStreamingGap(isStreaming, lastTokenAt);
  if (showGap) {
    return <WaveformIcon color="#818cf8" height={16} />;
  }
  return (
    <span className="ml-0.5 inline-block animate-pulse font-bold text-af-primary">
      ▌
    </span>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

type GeneratedAgent = {
  name: string;
  description: string;
  graph_definition: Record<string, unknown>;
  agent_model_config: Record<string, unknown>;
};

export default function ForgePage() {
  const router = useRouter();
  const [conversations, setConversations] = useState<ForgeConversation[]>([]);
  const [tabs, setTabs] = useState<TabState[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [loadingConvs, setLoadingConvs] = useState(true);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [designMode, setDesignMode] = useState(false);
  const [showPersonalization, setShowPersonalization] = useState(false);
  const [memoryCount, setMemoryCount] = useState(0);

  const abortRefs = useRef<Record<string, AbortController>>({});
  const inputRefs = useRef<Record<string, HTMLTextAreaElement | null>>({});
  const bottomRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const { activity, onLine: activityOnLine, reset: resetActivity, stepsRef } = useAgentActivity();

  // Load conversations on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await forgeListConversations();
        if (!cancelled) {
          setConversations(list);
          setLoadingConvs(false);
        }
      } catch (e) {
        if (!cancelled) {
          if (e instanceof ApiError && e.status === 401) {
            router.push("/login");
            return;
          }
          setGlobalError(e instanceof Error ? e.message : "Failed to load conversations");
          setLoadingConvs(false);
        }
      }
    })();
    return () => { cancelled = true; };
  }, [router]);

  useEffect(() => {
    getPreferences()
      .then((prefs) => {
        if (!prefs.onboarding_completed) {
          setShowPersonalization(true);
        }
      })
      .catch(() => {});
    api<{ count: number }>("/api/v1/forge/memory/count")
      .then((mc) => setMemoryCount(mc.count))
      .catch(() => {});
  }, []);

  // Auto-scroll active tab on new messages
  useEffect(() => {
    if (activeTabId) {
      bottomRefs.current[activeTabId]?.scrollIntoView({ behavior: "smooth" });
    }
  }, [activeTabId, tabs]);

  const activeTab = tabs.find((t) => t.convId === activeTabId) ?? null;

  // Open or focus a conversation tab — load history if not already open
  const openTab = useCallback((conv: ForgeConversation) => {
    setTabs((prev) => {
      if (prev.find((t) => t.convId === conv.id)) return prev;
      return [...prev, makeTab(conv.id, conv.provider, conv.model)];
    });
    setActiveTabId(conv.id);
    // Load existing messages in the background if the tab is new
    setTabs((prev) => {
      if (prev.find((t) => t.convId === conv.id)) return prev; // already open (race-safe)
      return prev; // will be loaded after the state update above settles
    });
    // Async load history for this tab
    forgeGetMessages(conv.id)
      .then((msgs) => {
        setTabs((prev) =>
          prev.map((t) => {
            if (t.convId !== conv.id || t.messages.length > 0) return t;
            const loaded: { role: "user" | "assistant"; content: string; timestamp: number }[] = msgs
              .filter((m) => m.role === "user" || m.role === "assistant")
              .map((m, i) => ({
                role: m.role as "user" | "assistant",
                content: m.content,
                timestamp: Date.now() - (msgs.length - i) * 1000,
              }));
            return { ...t, messages: loaded };
          }),
        );
      })
      .catch(() => {/* non-critical */});
  }, []);

  // Close a tab
  const closeTab = useCallback(
    (convId: string, e: React.MouseEvent) => {
      e.stopPropagation();
      abortRefs.current[convId]?.abort();
      delete abortRefs.current[convId];
      setTabs((prev) => {
        const next = prev.filter((t) => t.convId !== convId);
        if (activeTabId === convId) {
          setActiveTabId(next[next.length - 1]?.convId ?? null);
        }
        return next;
      });
    },
    [activeTabId],
  );

  // Create a new conversation and open it
  const handleNewConversation = useCallback(
    async (provider = DEFAULT_PROVIDER, model = DEFAULT_MODEL) => {
      try {
        const conv = await forgeCreateConversation(provider, model);
        setConversations((prev) => [conv, ...prev]);
        openTab(conv);
      } catch (e) {
        setGlobalError(e instanceof Error ? e.message : "Failed to create conversation");
      }
    },
    [openTab],
  );

  // Delete a conversation
  const handleDeleteConversation = useCallback(
    async (convId: string, e: React.MouseEvent) => {
      e.stopPropagation();
      if (!confirm("Delete this conversation?")) return;
      try {
        await forgeDeleteConversation(convId);
        setConversations((prev) => prev.filter((c) => c.id !== convId));
        abortRefs.current[convId]?.abort();
        delete abortRefs.current[convId];
        setTabs((prev) => {
          const next = prev.filter((t) => t.convId !== convId);
          if (activeTabId === convId) {
            setActiveTabId(next[next.length - 1]?.convId ?? null);
          }
          return next;
        });
      } catch (e) {
        setGlobalError(e instanceof Error ? e.message : "Failed to delete");
      }
    },
    [activeTabId],
  );

  // Update a single tab's state
  const patchTab = useCallback((convId: string, patch: Partial<TabState>) => {
    setTabs((prev) => prev.map((t) => (t.convId === convId ? { ...t, ...patch } : t)));
  }, []);

  // Send a message in the active tab (optionally bypass draft state)
  const handleSend = useCallback(
    async (convId: string, messageOverride?: string) => {
      const tab = tabs.find((t) => t.convId === convId);
      if (!tab || tab.loading) return;

      const userMsg = (messageOverride ?? tab.draft).trim();
      if (!userMsg) return;
      patchTab(convId, {
        draft: "",
        error: null,
        loading: true,
        messages: [
          ...tab.messages,
          { role: "user", content: userMsg, timestamp: Date.now() },
          { role: "assistant", content: "", streaming: true, timestamp: Date.now() },
        ],
      });

      abortRefs.current[convId]?.abort();
      abortRefs.current[convId] = new AbortController();
      const signal = abortRefs.current[convId].signal;

      try {
        const exec = await forgeExecute(convId, userMsg, tab.provider, tab.model);

        let accumulated = "";
        resetActivity();
        await consumeForgeSse(
          exec.execution_id,
          (event, dataJson) => {
            activityOnLine(event, dataJson);
            if (event === "token") {
              try {
                const parsed = JSON.parse(dataJson);
                accumulated += parsed?.text ?? parsed?.token ?? parsed?.content ?? dataJson;
              } catch {
                accumulated += dataJson;
              }
              setTabs((prev) =>
                prev.map((t) => {
                  if (t.convId !== convId) return t;
                  const msgs = t.messages.map((m, i) =>
                    i === t.messages.length - 1
                      ? { role: "assistant" as const, content: accumulated, streaming: true, timestamp: m.timestamp, lastTokenAt: Date.now() }
                      : m,
                  );
                  return { ...t, messages: msgs };
                }),
              );
            } else if (event === "done" || event === "completed") {
              setTabs((prev) =>
                prev.map((t) => {
                  if (t.convId !== convId) return t;
                  const msgs = t.messages.map((m, i) =>
                    i === t.messages.length - 1 ? { ...m, streaming: false } : m,
                  );
                  return { ...t, messages: msgs };
                }),
              );
            }
          },
          signal,
        );

        // Finalize — if accumulated is empty after stream, mark as failed
        const completedSteps = stepsRef.current;
        setTabs((prev) =>
          prev.map((t) => {
            if (t.convId !== convId) return t;
            const msgs = t.messages.map((m, i) =>
              i === t.messages.length - 1
                ? { ...m, streaming: false, failed: !accumulated, content: accumulated || m.content, steps: completedSteps }
                : m,
            );
            return { ...t, messages: msgs, loading: false };
          }),
        );

        // Refresh conversation list to update message count / last_message_at
        try {
          const list = await forgeListConversations();
          setConversations(list);
        } catch { /* non-critical */ }
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
        patchTab(convId, {
          loading: false,
          error: e instanceof Error ? e.message : "Request failed",
          messages: (tabs.find((t) => t.convId === convId)?.messages ?? []).filter(
            (m) => !(m.streaming && m.content === ""),
          ),
        });
      }
    },
    [tabs, patchTab, resetActivity, activityOnLine],
  );

  const handleInterruptDecision = useCallback(
    async (decisions: Parameters<React.ComponentProps<typeof InterruptPopup>["onDecided"]>[0]) => {
      const interrupt = activity.interrupt;
      if (!interrupt) return;
      try {
        await api(`/api/v1/executions/${interrupt.execution_id}/hitl`, {
          method: "POST",
          body: JSON.stringify({ decisions }),
        });
      } catch { /* non-critical */ }
    },
    [activity.interrupt],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>, convId: string) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend(convId);
    }
  };

  return (
    <ToolShell active="forge">
      <div className="flex h-[calc(100vh-4rem-2rem)] gap-0 overflow-hidden rounded-xl border border-af-border/40">
        {/* ── Sidebar ───────────────────────────────────────────────────────── */}
        <aside
          className={`flex shrink-0 flex-col border-r border-af-border/40 bg-af-surface-container/60 transition-all duration-200 ${
            sidebarCollapsed ? "w-12" : "w-72"
          }`}
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-af-border/40 px-3 py-3">
            {!sidebarCollapsed && (
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                  Forge
                </span>
                {memoryCount > 0 && (
                  <span
                    className="text-xs px-2 py-0.5 rounded-full font-medium"
                    style={{
                      background: "color-mix(in srgb, var(--af-accent) 12%, transparent)",
                      color: "var(--af-accent)",
                      border: "1px solid color-mix(in srgb, var(--af-accent) 30%, transparent)",
                    }}
                    title={`${memoryCount} memory chunks active`}
                  >
                    Memory ✦ {memoryCount}
                  </span>
                )}
              </div>
            )}
            <button
              type="button"
              onClick={() => setSidebarCollapsed((v) => !v)}
              className="ml-auto flex h-6 w-6 items-center justify-center rounded-md border border-af-border/60 text-af-muted transition-colors hover:border-af-primary hover:text-af-primary"
            >
              <span className="material-symbols-outlined text-sm">
                {sidebarCollapsed ? "chevron_right" : "chevron_left"}
              </span>
            </button>
          </div>

          {!sidebarCollapsed && (
            <>
              {/* New conversation buttons */}
              <div className="border-b border-af-border/40 p-3">
                <button
                  type="button"
                  onClick={() => void handleNewConversation()}
                  className="flex w-full items-center gap-2 rounded-lg border border-af-primary/40 bg-af-primary/10 px-3 py-2 text-xs font-bold text-af-primary transition-colors hover:bg-af-primary/20"
                >
                  <span className="material-symbols-outlined text-sm">add</span>
                  New conversation
                </button>
              </div>

              {/* Conversation list */}
              <div className="flex-1 overflow-y-auto">
                {loadingConvs && (
                  <p className="px-4 py-4 text-xs text-af-muted-dim">Loading…</p>
                )}
                {!loadingConvs && conversations.length === 0 && (
                  <div className="px-4 py-8 text-center">
                    <span className="material-symbols-outlined mb-2 text-2xl text-af-muted-dim">
                      bolt
                    </span>
                    <p className="text-xs text-af-muted-dim">No conversations yet.</p>
                  </div>
                )}
                {conversations.map((conv) => {
                  const isOpen = tabs.some((t) => t.convId === conv.id);
                  const isActive = activeTabId === conv.id;
                  return (
                    <div
                      key={conv.id}
                      onClick={() => openTab(conv)}
                      className={`group flex cursor-pointer flex-col gap-1 border-b border-af-border/20 px-4 py-3 transition-colors ${
                        isActive
                          ? "border-l-2 border-l-af-primary bg-af-primary/10"
                          : "hover:bg-white/[0.03]"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex min-w-0 flex-1 items-center gap-1.5">
                          <span className="material-symbols-outlined text-xs text-af-muted-dim">
                            {providerIcon(conv.provider)}
                          </span>
                          <span className="flex-1 truncate text-xs font-medium text-af-on-surface">
                            {conv.title ?? "New conversation"}
                          </span>
                          {isOpen && (
                            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-af-primary" />
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={(e) => void handleDeleteConversation(conv.id, e)}
                          className="invisible shrink-0 text-af-muted-dim transition-colors hover:text-af-error group-hover:visible"
                          title="Delete"
                        >
                          <span className="material-symbols-outlined text-sm">delete</span>
                        </button>
                      </div>
                      <div className="flex items-center gap-2 text-[10px] text-af-muted-dim">
                        <span className="font-mono">{conv.model.split("-").slice(0, 2).join("-")}</span>
                        <span>·</span>
                        <span>{conv.message_count} msgs</span>
                        {conv.last_message_at && (
                          <>
                            <span>·</span>
                            <span>{relativeDate(conv.last_message_at)}</span>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {sidebarCollapsed && (
            <div className="flex flex-col items-center gap-2 p-2 pt-3">
              <button
                type="button"
                title="New conversation"
                onClick={() => void handleNewConversation()}
                className="flex h-8 w-8 items-center justify-center rounded-full border border-af-primary/40 bg-af-primary/10 text-af-primary transition-colors hover:bg-af-primary/20"
              >
                <span className="material-symbols-outlined text-sm">add</span>
              </button>
            </div>
          )}
        </aside>

        {/* ── Main area ─────────────────────────────────────────────────────── */}
        <div className="flex flex-1 flex-col overflow-hidden bg-af-surface-container/20">
          {/* Tab bar */}
          {!designMode && tabs.length > 0 && (
            <div className="flex shrink-0 items-center gap-0 overflow-x-auto border-b border-af-border/40 bg-af-surface-void/40">
              {tabs.map((tab) => {
                const conv = conversations.find((c) => c.id === tab.convId);
                const isActive = tab.convId === activeTabId;
                return (
                  <button
                    key={tab.convId}
                    type="button"
                    onClick={() => setActiveTabId(tab.convId)}
                    className={`group flex shrink-0 items-center gap-2 border-r border-af-border/40 px-4 py-2.5 text-xs transition-colors ${
                      isActive
                        ? "border-b-2 border-b-af-primary bg-af-surface-container/60 text-af-primary"
                        : "text-af-muted hover:bg-white/[0.03] hover:text-af-on-surface"
                    }`}
                  >
                    <span className="material-symbols-outlined text-sm">
                      {providerIcon(tab.provider)}
                    </span>
                    <span className="max-w-[120px] truncate">
                      {conv?.title ?? "New conversation"}
                    </span>
                    {tab.loading && (
                      <span className="h-3 w-3 animate-spin rounded-full border border-af-primary border-t-transparent" />
                    )}
                    <span
                      onClick={(e) => closeTab(tab.convId, e)}
                      className="invisible ml-1 flex h-4 w-4 items-center justify-center rounded-full text-af-muted-dim transition-colors hover:bg-af-error/20 hover:text-af-error group-hover:visible"
                    >
                      <span className="material-symbols-outlined text-xs">close</span>
                    </span>
                  </button>
                );
              })}
              <button
                type="button"
                onClick={() => void handleNewConversation()}
                title="New conversation"
                className="flex h-full shrink-0 items-center px-3 text-af-muted-dim transition-colors hover:text-af-primary"
              >
                <span className="material-symbols-outlined text-sm">add</span>
              </button>
            </div>
          )}

          {/* Mode switcher (always visible) */}
          <div className="flex shrink-0 items-center justify-center gap-1 border-b border-af-border/40 p-2">
            <button
              type="button"
              onClick={() => setDesignMode(false)}
              className={`flex items-center gap-1.5 rounded-lg px-4 py-1.5 text-xs font-medium transition-all ${
                !designMode
                  ? "bg-af-primary/15 text-af-primary"
                  : "text-af-muted hover:text-af-on-surface"
              }`}
            >
              <span className="material-symbols-outlined text-sm">bolt</span>
              Chat
            </button>
            <button
              type="button"
              onClick={() => setDesignMode(true)}
              className={`flex items-center gap-1.5 rounded-lg px-4 py-1.5 text-xs font-medium transition-all ${
                designMode
                  ? "bg-af-primary/15 text-af-primary"
                  : "text-af-muted hover:text-af-on-surface"
              }`}
            >
              <span className="material-symbols-outlined text-sm">auto_awesome</span>
              Design
            </button>
          </div>

          {/* Design mode */}
          {designMode && (
            <ForgeDesignMode onAgentCreated={(id) => router.push(`/agents/${id}/builder`)} />
          )}

          {/* Empty state */}
          {!designMode && tabs.length === 0 && (
            <div className="flex flex-1 flex-col items-center justify-center gap-6 p-8 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-af-primary/30 bg-af-primary/10">
                <span className="material-symbols-outlined text-3xl text-af-primary">bolt</span>
              </div>
              <div>
                <h2 className="text-xl font-bold text-af-on-surface">Forge Assistant</h2>
                <p className="mt-2 max-w-sm text-sm text-af-muted">
                  Direct LLM chat with web search, Python REPL, and multi-turn memory. No agent required.
                </p>
              </div>
              <div className="flex flex-wrap justify-center gap-3">
                {PROVIDERS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => void handleNewConversation(p.id, p.models[0].id)}
                    className="flex items-center gap-2 rounded-lg border border-af-border/60 bg-af-surface-high px-4 py-2.5 text-xs text-af-muted transition-colors hover:border-af-primary/60 hover:text-af-primary"
                  >
                    <span className="material-symbols-outlined text-sm">{providerIcon(p.id)}</span>
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Active tab content */}
          {!designMode && activeTab && (
            <ForgeTabView
              tab={activeTab}
              bottomRef={(el) => { bottomRefs.current[activeTab.convId] = el; }}
              inputRef={(el) => { inputRefs.current[activeTab.convId] = el; }}
              onDraftChange={(v) => patchTab(activeTab.convId, { draft: v })}
              onProviderChange={(provider) => {
                const models = PROVIDERS.find((p) => p.id === provider)?.models ?? [];
                patchTab(activeTab.convId, { provider, model: models[0]?.id ?? DEFAULT_MODEL });
              }}
              onModelChange={(model) => patchTab(activeTab.convId, { model })}
              onSend={() => void handleSend(activeTab.convId)}
              onSendDirect={(msg) => void handleSend(activeTab.convId, msg)}
              onKeyDown={(e) => handleKeyDown(e, activeTab.convId)}
              activityToasts={activity.toasts}
              activityIsRunning={activity.isRunning}
            />
          )}
        </div>
      </div>

      {globalError && (
        <div className="fixed bottom-6 right-6 flex items-center gap-2 rounded-lg border border-af-error/30 bg-af-surface-high px-4 py-3 text-xs text-af-error shadow-lg">
          <span className="material-symbols-outlined text-sm">error</span>
          {globalError}
          <button
            type="button"
            onClick={() => setGlobalError(null)}
            className="ml-2 text-af-muted-dim hover:text-af-error"
          >
            <span className="material-symbols-outlined text-sm">close</span>
          </button>
        </div>
      )}

      {activity.interrupt && (
        <InterruptPopup
          executionId={activity.interrupt.execution_id}
          pendingTools={activity.interrupt.pending_tools}
          onDecided={handleInterruptDecision}
          onCancel={() => {
            if (activeTabId) abortRefs.current[activeTabId]?.abort();
          }}
        />
      )}

      {showPersonalization && (
        <PersonalizationOnboarding
          onComplete={() => setShowPersonalization(false)}
          onSkip={async () => {
            try {
              await updatePreferences({ onboarding_completed: true });
            } catch {
              // Non-critical
            }
            setShowPersonalization(false);
          }}
        />
      )}
    </ToolShell>
  );
}

// ── ForgeDesignMode ───────────────────────────────────────────────────────────

const DESIGN_EXAMPLES = [
  "A customer support agent that searches a knowledge base and escalates to human",
  "A research assistant that searches the web, summarizes findings, and writes a report",
  "A voice assistant that transcribes speech, answers questions, and speaks the reply",
  "A code review agent that analyzes PRs and posts comments on GitHub",
];

type NodePreview = { id: string; type: string; label?: string };

function ForgeDesignMode({ onAgentCreated }: { onAgentCreated: (id: string) => void }) {
  const [prompt, setPrompt] = useState("");
  const [generating, setGenerating] = useState(false);
  const [creating, setCreating] = useState(false);
  const [preview, setPreview] = useState<GeneratedAgent | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    if (!prompt.trim() || generating) return;
    setGenerating(true);
    setPreview(null);
    setError(null);
    try {
      const data = await api<GeneratedAgent>("/api/v1/generate/agent", {
        method: "POST",
        body: JSON.stringify({ prompt: prompt.trim() }),
      });
      setPreview(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  }

  async function handleCreate() {
    if (!preview || creating) return;
    setCreating(true);
    setError(null);
    try {
      const agent = await api<{ id: string }>("/api/v1/agents", {
        method: "POST",
        body: JSON.stringify({
          name: preview.name,
          description: preview.description,
          graph_definition: preview.graph_definition,
          model_config: preview.agent_model_config,
        }),
      });
      onAgentCreated(agent.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create agent");
      setCreating(false);
    }
  }

  // Parse nodes from graph_definition for preview
  const nodePreview: NodePreview[] = (() => {
    if (!preview) return [];
    const gd = preview.graph_definition as { nodes?: { id: string; type?: string; label?: string }[] };
    return (gd.nodes ?? []).map((n) => ({ id: n.id, type: n.type ?? "llm", label: n.label ?? n.id }));
  })();

  const nodeTypeColor: Record<string, string> = {
    llm: "#c3c0ff",
    tool: "#86efac",
    conditional: "#fde68a",
    interrupt: "#fca5a5",
    subagent: "#a5b4fc",
    asr: "#6ee7b7",
    tts: "#93c5fd",
  };

  return (
    <div className="flex flex-1 flex-col overflow-y-auto p-8">
      <div className="mx-auto w-full max-w-2xl">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-af-primary/30 bg-gradient-to-br from-af-primary/20 to-purple-600/10">
            <span className="material-symbols-outlined text-3xl text-af-primary">auto_awesome</span>
          </div>
          <h2 className="text-2xl font-bold text-af-on-surface">Design an Agent</h2>
          <p className="mt-2 text-sm text-af-muted">
            Describe what your agent should do in plain language. AI will generate the graph.
          </p>
        </div>

        {/* Input */}
        <div className="relative">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                void handleGenerate();
              }
            }}
            placeholder="Describe your agent… e.g. 'A research assistant that searches the web and summarizes results'"
            rows={4}
            disabled={generating}
            className="w-full rounded-xl border border-af-border/60 bg-af-surface-high px-4 py-3 text-sm text-af-on-surface placeholder:text-af-muted-dim focus:border-af-primary/60 focus:outline-none focus:shadow-[0_0_0_3px_rgba(124,58,237,0.12)] disabled:opacity-50 resize-none"
          />
          <div className="absolute bottom-3 right-3">
            <button
              type="button"
              onClick={() => void handleGenerate()}
              disabled={!prompt.trim() || generating}
              className="flex items-center gap-1.5 rounded-lg bg-af-primary px-4 py-1.5 text-xs font-bold text-black transition-all hover:opacity-90 disabled:opacity-40"
            >
              {generating ? (
                <>
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-black border-t-transparent" />
                  Generating…
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined text-sm">auto_awesome</span>
                  Generate
                </>
              )}
            </button>
          </div>
        </div>
        <p className="mt-1.5 text-right text-[10px] text-af-muted-dim">⌘Enter to generate</p>

        {/* Example prompts */}
        {!preview && !generating && (
          <div className="mt-6">
            <p className="mb-3 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
              Examples
            </p>
            <div className="flex flex-col gap-2">
              {DESIGN_EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => setPrompt(ex)}
                  className="flex items-start gap-2 rounded-lg border border-af-border/40 bg-af-surface-high px-3 py-2.5 text-left text-xs text-af-muted transition-colors hover:border-af-primary/40 hover:text-af-on-surface"
                >
                  <span className="material-symbols-outlined mt-0.5 shrink-0 text-sm text-af-muted-dim">
                    chevron_right
                  </span>
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-af-error/30 bg-af-error/10 px-4 py-3 text-xs text-af-error">
            <span className="material-symbols-outlined text-sm">error</span>
            {error}
          </div>
        )}

        {/* Preview card */}
        {preview && (
          <div className="mt-6 overflow-hidden rounded-xl border border-af-primary/30 bg-af-surface-high shadow-[0_0_40px_-8px_rgba(124,58,237,0.25)]">
            {/* Agent header */}
            <div className="border-b border-af-border/40 bg-af-primary/5 px-5 py-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="text-base font-bold text-af-on-surface">{preview.name}</h3>
                  <p className="mt-0.5 text-xs text-af-muted">{preview.description}</p>
                </div>
                <span className="shrink-0 rounded-full border border-af-primary/30 bg-af-primary/10 px-2.5 py-0.5 text-[10px] font-bold text-af-primary">
                  Preview
                </span>
              </div>
            </div>

            {/* Node graph preview */}
            <div className="px-5 py-4">
              <p className="mb-3 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                Graph — {nodePreview.length} node{nodePreview.length !== 1 ? "s" : ""}
              </p>
              <div className="flex flex-wrap gap-2">
                {nodePreview.map((node, i) => (
                  <div
                    key={node.id}
                    className="flex items-center gap-1.5 rounded-lg border border-af-border/40 bg-af-surface px-3 py-1.5 text-xs"
                    style={{ animationDelay: `${i * 50}ms` }}
                  >
                    <span
                      className="h-2 w-2 rounded-full shrink-0"
                      style={{ backgroundColor: nodeTypeColor[node.type] ?? "#94a3b8" }}
                    />
                    <span className="text-af-on-surface font-medium">{node.label}</span>
                    <span className="text-af-muted-dim">·</span>
                    <span className="text-af-muted-dim font-mono">{node.type}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between border-t border-af-border/40 px-5 py-3">
              <button
                type="button"
                onClick={() => { setPreview(null); setError(null); }}
                className="text-xs text-af-muted transition-colors hover:text-af-on-surface"
              >
                ← Try again
              </button>
              <button
                type="button"
                onClick={() => void handleCreate()}
                disabled={creating}
                className="flex items-center gap-1.5 rounded-lg bg-af-primary px-5 py-2 text-xs font-bold text-black transition-all hover:opacity-90 disabled:opacity-50"
              >
                {creating ? (
                  <>
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-black border-t-transparent" />
                    Creating…
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined text-sm">open_in_new</span>
                    Create &amp; Open Builder
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── ForgeTabView ──────────────────────────────────────────────────────────────

function ForgeTabView({
  tab,
  bottomRef,
  inputRef,
  onDraftChange,
  onProviderChange,
  onModelChange,
  onSend,
  onSendDirect,
  onKeyDown,
  activityToasts,
  activityIsRunning,
}: {
  tab: TabState;
  bottomRef: (el: HTMLDivElement | null) => void;
  inputRef: (el: HTMLTextAreaElement | null) => void;
  onDraftChange: (v: string) => void;
  onProviderChange: (p: string) => void;
  onModelChange: (m: string) => void;
  onSend: () => void;
  onSendDirect: (msg: string) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  activityToasts: AgentStep[];
  activityIsRunning: boolean;
}) {
  const currentProvider = PROVIDERS.find((p) => p.id === tab.provider) ?? PROVIDERS[0];
  const modelOptions = currentProvider.models;

  // Slash command palette state
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  const [cmdFilter, setCmdFilter] = useState("");
  const [cmdHighlight, setCmdHighlight] = useState(0);

  const filteredCommands = SLASH_COMMANDS.filter(
    (c) =>
      c.command.includes(cmdFilter) ||
      c.description.toLowerCase().includes(cmdFilter.toLowerCase()),
  );

  function handleDraftChange(v: string) {
    onDraftChange(v);
    if (v.startsWith("/")) {
      setCmdPaletteOpen(true);
      setCmdFilter(v.slice(1));
      setCmdHighlight(0);
    } else {
      setCmdPaletteOpen(false);
      setCmdFilter("");
    }
  }

  function selectCommand(cmd: SlashCommand) {
    // For commands that need a suffix (search, python) keep them in draft; others send immediately
    const needsSuffix = cmd.command === "/search" || cmd.command === "/python";
    if (needsSuffix) {
      onDraftChange(cmd.message);
      setCmdPaletteOpen(false);
    } else {
      onSendDirect(cmd.message);
      onDraftChange("");
      setCmdPaletteOpen(false);
    }
  }

  function handlePaletteKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (!cmdPaletteOpen) {
      onKeyDown(e);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCmdHighlight((h) => Math.min(h + 1, filteredCommands.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCmdHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (filteredCommands[cmdHighlight]) {
        selectCommand(filteredCommands[cmdHighlight]);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setCmdPaletteOpen(false);
    } else {
      onKeyDown(e);
    }
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="flex shrink-0 items-center gap-3 border-b border-af-border/40 px-4 py-2">
        <span className="material-symbols-outlined text-sm text-af-muted-dim">
          {providerIcon(tab.provider)}
        </span>
        <select
          value={tab.provider}
          onChange={(e) => onProviderChange(e.target.value)}
          disabled={tab.loading}
          className="rounded-md border border-af-border/60 bg-transparent px-2 py-1 text-xs text-af-on-surface focus:border-af-primary focus:outline-none disabled:opacity-50"
        >
          {PROVIDERS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
        <select
          value={tab.model}
          onChange={(e) => onModelChange(e.target.value)}
          disabled={tab.loading}
          className="rounded-md border border-af-border/60 bg-transparent px-2 py-1 text-xs text-af-on-surface focus:border-af-primary focus:outline-none disabled:opacity-50"
        >
          {modelOptions.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
        <span className="ml-auto text-[10px] text-af-muted-dim">
          {tab.messages.filter((m) => m.role === "user").length} turns
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {tab.messages.length === 0 && (
          <div className="af-motion-fade-in flex h-full flex-col items-center justify-center gap-5 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-af-primary/30 bg-af-primary/10">
              <span className="material-symbols-outlined text-2xl text-af-primary">
                {providerIcon(tab.provider)}
              </span>
            </div>
            <div>
              <p className="text-base font-bold text-af-on-surface">{currentProvider.label}</p>
              <p className="mt-1 text-xs text-af-muted">
                <span className="af-mono">{tab.model}</span> · web search · Python REPL · multi-turn memory
              </p>
            </div>
            <div className="flex max-w-lg flex-wrap justify-center gap-2">
              {[
                { label: "What can you do?", icon: "help" },
                { label: "Search the web for latest AI news", icon: "search" },
                { label: "Write a Python fibonacci script", icon: "code" },
                { label: "Help me with AgentForge SDK", icon: "terminal" },
              ].map((s) => (
                <button
                  key={s.label}
                  type="button"
                  onClick={() => onSendDirect(s.label)}
                  className="flex items-center gap-1.5 rounded-full border border-af-border/60 bg-af-surface-high px-3 py-1.5 text-xs text-af-muted transition-colors hover:border-af-primary/60 hover:text-af-primary"
                >
                  <span className="material-symbols-outlined text-sm">{s.icon}</span>
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-col gap-3">
          {tab.messages.map((msg, idx) => {
            const isUser = msg.role === "user";
            return (
              <div key={idx} className={`group flex ${isUser ? "justify-end" : "justify-start"}`}>
                {!isUser && (
                  <div className="mr-2 mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-af-primary/30 bg-af-primary/10">
                    <span className="material-symbols-outlined text-xs text-af-primary">
                      {providerIcon(tab.provider)}
                    </span>
                  </div>
                )}
                <div className="flex max-w-[82%] flex-col gap-1">
                  <div
                    className={`rounded-2xl px-3 py-2.5 text-sm leading-relaxed ${
                      isUser
                        ? "bg-af-primary text-black"
                        : "border border-af-border/60 bg-af-surface-high text-af-on-surface"
                    }`}
                  >
                    <div>
                      {msg.failed && !msg.streaming ? (
                        <span className="italic text-af-error">
                          An error occurred. Please try again.
                        </span>
                      ) : isUser ? (
                        <span className="whitespace-pre-wrap">{msg.content}</span>
                      ) : (
                        <>
                          {msg.content && (
                            <MarkdownMessage content={msg.content} className="prose-invert text-sm leading-relaxed" />
                          )}
                          {msg.streaming && msg.content && (
                            <StreamingCursor isStreaming={msg.streaming} lastTokenAt={msg.lastTokenAt} />
                          )}
                        </>
                      )}
                      {msg.streaming && !msg.content && (
                        <span className="flex items-center gap-2 py-1">
                          {/* Waveform bars */}
                          <span className="flex items-end gap-[2px] h-4">
                            {[0.4, 0.75, 1, 0.85, 0.6].map((h, i) => (
                              <span
                                key={i}
                                className="w-[2.5px] rounded-full bg-indigo-400 block"
                                style={{
                                  height: `${h * 14}px`,
                                  animation: `af-wave 1s ${i * 0.1}s ease-in-out infinite`,
                                  transformOrigin: "bottom",
                                }}
                              />
                            ))}
                          </span>
                          <span className="text-[11px] text-af-muted animate-pulse">thinking…</span>
                          <style>{`@keyframes af-wave { 0%,100%{transform:scaleY(.35)} 50%{transform:scaleY(1)} }`}</style>
                        </span>
                      )}
                    </div>
                  </div>
                  {msg.role === "assistant" && msg.steps && msg.steps.length > 0 && (
                    <AgentStepChips steps={msg.steps} />
                  )}
                  <span
                    className={`px-1 text-[10px] text-af-muted-dim opacity-0 transition-opacity group-hover:opacity-100 ${
                      isUser ? "text-right" : "text-left"
                    }`}
                  >
                    {timeAgo(msg.timestamp)}
                  </span>
                </div>
                {isUser && (
                  <div className="ml-2 mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-af-border/60 bg-af-surface-high text-af-muted">
                    <span className="material-symbols-outlined text-xs">person</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {tab.error && (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-af-error/30 bg-af-error/10 px-4 py-2 text-xs text-af-error">
            <span className="material-symbols-outlined text-sm">error</span>
            {tab.error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Agent activity toasts */}
      <AgentToastStack toasts={activityToasts} isRunning={activityIsRunning} />

      {/* Input */}
      <div className="shrink-0 border-t border-af-border/40 p-4">
        <div className="relative">
          {/* Slash command palette */}
          {cmdPaletteOpen && filteredCommands.length > 0 && (
            <div className="absolute bottom-full mb-2 w-full overflow-hidden rounded-xl border border-af-border/60 bg-af-surface-high shadow-xl">
              <div className="border-b border-af-border/30 px-3 py-1.5">
                <span className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                  Commands
                </span>
              </div>
              <div className="max-h-60 overflow-y-auto">
                {filteredCommands.map((cmd, i) => (
                  <button
                    key={cmd.command}
                    type="button"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      selectCommand(cmd);
                    }}
                    className={`flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors ${
                      i === cmdHighlight
                        ? "bg-af-primary/15 text-af-primary"
                        : "text-af-on-surface hover:bg-white/[0.04]"
                    }`}
                  >
                    <span
                      className={`material-symbols-outlined text-sm ${
                        i === cmdHighlight ? "text-af-primary" : "text-af-muted-dim"
                      }`}
                    >
                      {cmd.icon}
                    </span>
                    <div className="min-w-0 flex-1">
                      <span className="block text-xs font-medium">{cmd.command}</span>
                      <span className="block truncate text-[10px] text-af-muted-dim">
                        {cmd.description}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="flex items-end gap-3 rounded-xl border border-af-border/60 bg-af-surface-high px-4 py-3 transition-all focus-within:border-af-primary/60 focus-within:shadow-[0_0_0_3px_rgba(124,58,237,0.12)]">
            <textarea
              ref={inputRef}
              value={tab.draft}
              onChange={(e) => handleDraftChange(e.target.value)}
              onKeyDown={handlePaletteKeyDown}
              placeholder="Message Forge… (Enter to send, Shift+Enter for newline, / for commands)"
              disabled={tab.loading}
              rows={1}
              className="max-h-40 flex-1 resize-none bg-transparent text-sm text-af-on-surface placeholder:text-af-muted-dim focus:outline-none disabled:opacity-50"
              style={{ minHeight: "1.5rem" }}
            />
            <div className="flex shrink-0 items-center gap-2">
              {tab.draft.length > 0 && !cmdPaletteOpen && (
                <span className="text-[10px] text-af-muted-dim">{tab.draft.length}</span>
              )}
              {!tab.draft && (
                <button
                  type="button"
                  title="Slash commands"
                  onClick={() => handleDraftChange("/")}
                  disabled={tab.loading}
                  className="flex h-7 w-7 items-center justify-center rounded-md text-af-muted-dim transition-colors hover:text-af-primary disabled:opacity-40"
                >
                  <span className="material-symbols-outlined text-base">slash</span>
                </button>
              )}
              <button
                type="button"
                onClick={onSend}
                disabled={!tab.draft.trim() || tab.loading}
                className="flex h-8 w-8 items-center justify-center rounded-lg bg-af-primary text-black transition-all hover:opacity-90 disabled:opacity-40"
              >
                {tab.loading ? (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-black border-t-transparent" />
                ) : (
                  <span className="material-symbols-outlined text-sm">send</span>
                )}
              </button>
            </div>
          </div>
        </div>
        <p className="mt-1.5 text-center text-[10px] text-af-muted-dim">
          Type <kbd className="rounded border border-af-border/40 bg-af-surface px-1 font-mono">/</kbd> for commands · Web search · Python REPL · Multi-turn memory
        </p>
      </div>
    </div>
  );
}
