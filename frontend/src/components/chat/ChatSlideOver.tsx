"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Conversation,
  api,
  createConversation,
  deleteConversation,
  executeAgent,
  listConversations,
} from "@/lib/api";
import { consumeExecutionSse } from "@/lib/sse";
import { useChatContext } from "@/contexts/ChatContext";

type Agent = {
  id: string;
  name: string;
  status: string;
  description: string | null;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  timestamp: number;
};

function timeAgo(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 60) return "now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

const PROMPT_SUGGESTIONS = [
  "Que peux-tu faire pour moi ?",
  "Résume tes capacités en 3 points.",
  "Donne-moi un exemple d'usage concret.",
  "Quelles sont tes limites ?",
];

export function ChatSlideOver() {
  const { isOpen, selectedAgentId, setSelectedAgentId, closeChat } = useChatContext();

  const [agents, setAgents] = useState<Agent[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showConvList, setShowConvList] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input when open
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen]);

  // Escape + Tab focus trap when open
  useEffect(() => {
    if (!isOpen) return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closeChat();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;

      const focusable = panelRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      const list = Array.from(focusable);
      if (list.length === 0) return;

      const first = list[0];
      const last = list[list.length - 1];
      const active = document.activeElement as HTMLElement | null;
      const inside = active && panelRef.current.contains(active);

      if (e.shiftKey) {
        if (!inside || active === first || !list.includes(active!)) {
          e.preventDefault();
          last.focus();
        }
      } else if (!inside || active === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [isOpen, closeChat]);

  const selectedAgentIdRef = useRef(selectedAgentId);
  selectedAgentIdRef.current = selectedAgentId;

  const syncAgentsAndSelection = useCallback(
    async () => {
      try {
        const data = await api<Agent[]>("/api/v1/agents");
        setAgents(data);
        const cur = selectedAgentIdRef.current;
        if (cur && data.some((a) => a.id === cur)) return;
        setSelectedAgentId(data[0]?.id ?? null);
      } catch {
        setAgents([]);
      }
    },
    [setSelectedAgentId],
  );

  // Load agents on mount (FAB label, etc.)
  useEffect(() => {
    void syncAgentsAndSelection();
  }, [syncAgentsAndSelection]);

  // Re-fetch when panel opens so a post-login session gets the full list (mount may have been 401)
  useEffect(() => {
    if (!isOpen) return;
    void syncAgentsAndSelection();
  }, [isOpen, syncAgentsAndSelection]);

  // Load conversations when agent changes
  useEffect(() => {
    if (!selectedAgentId) {
      setConversations([]);
      setActiveConversation(null);
      setMessages([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const convs = await listConversations(selectedAgentId);
        if (!cancelled) {
          setConversations(convs);
          setActiveConversation(null);
          setMessages([]);
        }
      } catch {
        if (!cancelled) setConversations([]);
      }
    })();
    return () => { cancelled = true; };
  }, [selectedAgentId]);

  const handleNewConversation = useCallback(async () => {
    if (!selectedAgentId) return;
    try {
      const conv = await createConversation(selectedAgentId);
      setConversations((prev) => [conv, ...prev]);
      setActiveConversation(conv);
      setMessages([]);
      setShowConvList(false);
    } catch {
      /* ignore */
    }
  }, [selectedAgentId]);

  const handleDeleteConversation = useCallback(
    async (convId: string, e: React.MouseEvent) => {
      e.stopPropagation();
      if (!selectedAgentId) return;
      if (!confirm("Delete this conversation?")) return;
      try {
        await deleteConversation(selectedAgentId, convId);
        setConversations((prev) => prev.filter((c) => c.id !== convId));
        if (activeConversation?.id === convId) {
          setActiveConversation(null);
          setMessages([]);
        }
      } catch {
        /* ignore */
      }
    },
    [selectedAgentId, activeConversation],
  );

  const handleSend = useCallback(async (overrideInput?: string) => {
    const userMsg = (overrideInput ?? input).trim();
    if (!userMsg || !selectedAgentId || isLoading) return;

    setInput("");
    setError(null);

    let conv = activeConversation;
    if (!conv) {
      try {
        conv = await createConversation(selectedAgentId, userMsg.slice(0, 60));
        setConversations((prev) => [conv!, ...prev]);
        setActiveConversation(conv);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to create conversation");
        return;
      }
    }

    const now = Date.now();
    setMessages((prev) => [...prev, { role: "user", content: userMsg, timestamp: now }]);
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", streaming: true, timestamp: Date.now() },
    ]);
    setIsLoading(true);

    abortRef.current?.abort();
    abortRef.current = new AbortController();
    const signal = abortRef.current.signal;

    try {
      const exec = await executeAgent(selectedAgentId, userMsg, conv.thread_id, true);

      if (exec.status !== "running") {
        const assistantContent =
          exec.output_messages?.find((m) => m.role === "assistant")?.content ?? "";
        setMessages((prev) =>
          prev.map((m, i) =>
            i === prev.length - 1
              ? { role: "assistant", content: assistantContent, timestamp: Date.now() }
              : m,
          ),
        );
      } else {
        let accumulated = "";
        await consumeExecutionSse(
          selectedAgentId,
          exec.id,
          (event, dataJson) => {
            if (event === "token") {
              try {
                const parsed = JSON.parse(dataJson);
                const token = parsed?.token ?? parsed?.content ?? dataJson;
                accumulated += token;
              } catch {
                accumulated += dataJson;
              }
              setMessages((prev) =>
                prev.map((m, i) =>
                  i === prev.length - 1
                    ? { role: "assistant", content: accumulated, streaming: true, timestamp: m.timestamp }
                    : m,
                ),
              );
            } else if (event === "done" || event === "completed") {
              setMessages((prev) =>
                prev.map((m, i) =>
                  i === prev.length - 1 ? { ...m, streaming: false } : m,
                ),
              );
            }
          },
          signal,
        );

        try {
          const final = await api<{
            output_messages: { role: string; content: string }[] | null;
          }>(`/api/v1/agents/${selectedAgentId}/executions/${exec.id}`);
          const finalContent =
            final.output_messages?.filter((m) => m.role === "assistant").pop()?.content ??
            accumulated;
          setMessages((prev) =>
            prev.map((m, i) =>
              i === prev.length - 1
                ? { role: "assistant", content: finalContent, streaming: false, timestamp: m.timestamp }
                : m,
            ),
          );
        } catch {
          setMessages((prev) =>
            prev.map((m, i) =>
              i === prev.length - 1
                ? { role: "assistant", content: accumulated, streaming: false, timestamp: m.timestamp }
                : m,
            ),
          );
        }
      }

      try {
        const convs = await listConversations(selectedAgentId);
        setConversations(convs);
        setActiveConversation((prev) => {
          if (!prev) return null;
          return convs.find((c) => c.id === prev.id) ?? prev;
        });
      } catch {
        /* non-critical */
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setError(e instanceof Error ? e.message : "Execute failed");
      setMessages((prev) => prev.filter((m) => !(m.streaming && m.content === "")));
    } finally {
      setIsLoading(false);
    }
  }, [input, selectedAgentId, activeConversation, isLoading]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  const selectedAgent = agents.find((a) => a.id === selectedAgentId);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={closeChat}
        className={`fixed inset-0 z-40 bg-black/40 backdrop-blur-md transition-opacity duration-300 ${
          isOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        aria-hidden="true"
      />

      {/* Slide-over panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={
          selectedAgent
            ? `Chat avec ${selectedAgent.name}`
            : "Panneau de chat"
        }
        aria-hidden={!isOpen}
        className={`fixed right-0 top-0 z-50 flex h-full w-full flex-col border-l border-af-border bg-af-surface-void/95 shadow-2xl backdrop-blur-xl transition-transform duration-300 ease-out sm:w-[420px] ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex shrink-0 items-center gap-2 border-b border-af-border/80 bg-af-surface-high/40 px-4 py-3 backdrop-blur-sm">
          {/* Agent selector */}
          <div className="flex flex-1 items-center gap-2 min-w-0">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-af-primary/40 bg-af-primary/10">
              <span className="material-symbols-outlined text-sm text-af-primary">smart_toy</span>
            </div>
            <select
              value={selectedAgentId ?? ""}
              onChange={(e) => setSelectedAgentId(e.target.value || null)}
              className="flex-1 min-w-0 truncate rounded-md border border-af-border/60 bg-af-surface-high px-2 py-1.5 text-sm text-af-on-surface focus:border-af-primary focus:outline-none"
            >
              {agents.length === 0 && <option value="">No agents</option>}
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>

          {/* Conversation list toggle */}
          <button
            type="button"
            title="Conversations"
            onClick={() => setShowConvList((v) => !v)}
            className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md border transition-colors ${
              showConvList
                ? "border-af-primary/60 bg-af-primary/10 text-af-primary"
                : "border-af-border/60 text-af-muted hover:border-af-primary hover:text-af-primary"
            }`}
          >
            <span className="material-symbols-outlined text-sm">history</span>
          </button>

          {/* New conversation */}
          <button
            type="button"
            title="New conversation"
            onClick={() => void handleNewConversation()}
            disabled={!selectedAgentId}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-af-border/60 text-af-muted transition-colors hover:border-af-primary hover:text-af-primary disabled:opacity-40"
          >
            <span className="material-symbols-outlined text-sm">add</span>
          </button>

          {/* Close */}
          <button
            type="button"
            onClick={closeChat}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-af-border/60 text-af-muted transition-colors hover:border-af-error hover:text-af-error"
          >
            <span className="material-symbols-outlined text-sm">close</span>
          </button>
        </div>

        {/* Conversation list (collapsible) */}
        {showConvList && (
          <div className="shrink-0 max-h-48 overflow-y-auto border-b border-af-border/40 bg-af-surface-low">
            {conversations.length === 0 && (
              <p className="px-4 py-3 text-xs text-af-muted-dim">No conversations yet.</p>
            )}
            {conversations.map((conv, idx) => {
              const active = activeConversation?.id === conv.id;
              return (
                <div
                  key={conv.id}
                  onClick={() => {
                    setActiveConversation(conv);
                    setMessages([]);
                    setShowConvList(false);
                  }}
                  className={`group flex cursor-pointer items-center justify-between gap-2 border-b border-af-border/20 px-4 py-2.5 transition-colors ${
                    active
                      ? "bg-af-primary/10 border-l-2 border-l-af-primary"
                      : "hover:bg-white/[0.03]"
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-af-on-surface">
                      {conv.title ?? `Conversation #${idx + 1}`}
                    </p>
                    <p className="text-[10px] text-af-muted-dim">
                      {conv.message_count ?? 0} msgs
                      {conv.last_message_at && ` · ${new Date(conv.last_message_at).toLocaleDateString()}`}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => void handleDeleteConversation(conv.id, e)}
                    className="invisible shrink-0 text-af-muted-dim transition-colors hover:text-af-error group-hover:visible"
                  >
                    <span className="material-symbols-outlined text-sm">delete</span>
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* Active conversation label */}
        {activeConversation && (
          <div className="shrink-0 flex items-center gap-2 border-b border-af-border/30 bg-af-surface-low px-4 py-1.5">
            <span className="material-symbols-outlined text-xs text-af-muted-dim">forum</span>
            <span className="truncate text-[10px] text-af-muted-dim font-mono">
              {activeConversation.title ?? "Untitled"} · thread:{activeConversation.thread_id.slice(0, 8)}…
            </span>
          </div>
        )}

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          {/* Empty state */}
          {selectedAgentId && messages.length === 0 && !isLoading && (
            <div className="flex h-full flex-col items-center justify-center gap-6 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full border border-af-primary/30 bg-af-primary/10">
                <span className="material-symbols-outlined text-2xl text-af-primary">smart_toy</span>
              </div>
              <div>
                <p className="text-sm font-medium text-af-on-surface">
                  {selectedAgent?.name ?? "Agent"}
                </p>
                <p className="mt-1 text-xs text-af-muted-dim">
                  {selectedAgent?.description ?? "Que puis-je faire pour toi ?"}
                </p>
              </div>
              {/* Suggestion chips */}
              <div className="flex flex-wrap justify-center gap-2">
                {PROMPT_SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => void handleSend(s)}
                    className="rounded-full border border-af-border/60 bg-af-surface-high px-3 py-1.5 text-xs text-af-muted transition-colors hover:border-af-primary/60 hover:text-af-primary"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {!selectedAgentId && (
            <div className="flex h-full items-center justify-center">
              <p className="text-sm text-af-muted-dim">Select an agent to start chatting.</p>
            </div>
          )}

          {/* Message list */}
          <div className="flex flex-col gap-3">
            {messages.map((msg, idx) => {
              const isUser = msg.role === "user";
              return (
                <div key={idx} className={`group flex ${isUser ? "justify-end" : "justify-start"}`}>
                  {!isUser && (
                    <div className="mr-2 mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-af-primary/30 bg-af-primary/10">
                      <span className="material-symbols-outlined text-xs text-af-primary">
                        smart_toy
                      </span>
                    </div>
                  )}
                  <div className="flex flex-col gap-1 max-w-[82%]">
                    <div
                      className={`rounded-2xl px-3 py-2.5 text-sm leading-relaxed ${
                        isUser
                          ? "bg-af-primary text-black"
                          : "border border-af-border/60 bg-af-surface-high text-af-on-surface"
                      }`}
                    >
                      <div className="whitespace-pre-wrap">
                        {msg.content}
                        {msg.streaming && (
                          <span className="ml-0.5 inline-block animate-pulse font-bold text-af-primary">
                            ▌
                          </span>
                        )}
                        {msg.streaming && msg.content === "" && (
                          <span className="flex gap-1 py-0.5">
                            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-af-muted [animation-delay:0ms]" />
                            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-af-muted [animation-delay:150ms]" />
                            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-af-muted [animation-delay:300ms]" />
                          </span>
                        )}
                      </div>
                    </div>
                    <span className="px-1 text-[10px] text-af-muted-dim opacity-0 transition-opacity group-hover:opacity-100">
                      {timeAgo(msg.timestamp)}
                    </span>
                  </div>
                  {isUser && (
                    <div className="ml-2 mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-af-border/60 bg-af-surface-high">
                      <span className="material-symbols-outlined text-xs text-af-muted">person</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Error */}
          {error && (
            <div className="mt-3 rounded-lg border border-af-error/30 bg-af-error/10 px-3 py-2 text-xs text-af-error">
              {error}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div className="shrink-0 border-t border-af-border/40 p-3">
          <div className="flex items-end gap-2 rounded-xl border border-af-border/60 bg-af-surface-high px-3 py-2 focus-within:border-af-primary/60 transition-colors">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                selectedAgentId
                  ? "Message… (Enter to send)"
                  : "Select an agent first"
              }
              disabled={!selectedAgentId || isLoading}
              rows={1}
              className="max-h-32 flex-1 resize-none bg-transparent text-sm text-af-on-surface placeholder:text-af-muted-dim focus:outline-none disabled:opacity-50"
              style={{ minHeight: "1.25rem" }}
            />
            <button
              type="button"
              onClick={() => void handleSend()}
              disabled={!input.trim() || !selectedAgentId || isLoading}
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-af-primary text-black transition-all hover:opacity-90 disabled:opacity-40"
            >
              {isLoading ? (
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-black border-t-transparent" />
              ) : (
                <span className="material-symbols-outlined text-sm">send</span>
              )}
            </button>
          </div>
          <p className="mt-1 text-center text-[10px] text-af-muted-dim">
            Shift+Enter for newline · conversations are persisted · ⌘J / Ctrl+J
            pour ouvrir ou fermer
          </p>
        </div>
      </div>
    </>
  );
}
