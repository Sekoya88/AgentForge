"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import {
  ApiError,
  Conversation,
  api,
  createConversation,
  deleteConversation,
  executeAgent,
  listConversations,
} from "@/lib/api";
import { consumeExecutionSse } from "@/lib/sse";

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
  if (diff < 5) return "now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function relativeDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const diff = Math.floor((now.getTime() - d.getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 172800) return "yesterday";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

const PROMPT_SUGGESTIONS = [
  "Que peux-tu faire pour moi ?",
  "Résume tes capacités.",
  "Donne-moi un exemple concret.",
  "Montre-moi comment tu travailles.",
];

function AgentAvatar({ name }: { name: string }) {
  const initials = name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
  return (
    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-af-primary/30 bg-gradient-to-br from-af-primary/20 to-af-secondary/20 text-xs font-bold text-af-primary">
      {initials || "A"}
    </div>
  );
}

function ChatPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Load agents on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api<Agent[]>("/api/v1/agents");
        if (!cancelled) {
          setAgents(data);
          const paramId = searchParams.get("agent");
          if (paramId && data.find((a) => a.id === paramId)) {
            setSelectedAgentId(paramId);
          } else if (data.length > 0) {
            setSelectedAgentId(data[0].id);
          }
        }
      } catch (e) {
        if (!cancelled) {
          if (e instanceof ApiError && e.status === 401) {
            router.push("/login");
            return;
          }
          setError(e instanceof Error ? e.message : "Failed to load agents");
        }
      }
    })();
    return () => { cancelled = true; };
  }, [router, searchParams]);

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
      inputRef.current?.focus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create conversation");
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
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to delete conversation");
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
    <ToolShell active="chat">
      <div className="flex h-[calc(100vh-4rem-2rem)] gap-0 overflow-hidden rounded-xl border border-af-border/40">
        {/* Sidebar */}
        <aside
          className={`flex shrink-0 flex-col border-r border-af-border/40 bg-af-surface-container/60 transition-all duration-200 ${
            sidebarCollapsed ? "w-12" : "w-72"
          }`}
        >
          {/* Collapse toggle */}
          <div className="flex items-center justify-between border-b border-af-border/40 px-3 py-3">
            {!sidebarCollapsed && (
              <span className="text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                Workspace
              </span>
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
              {/* Agent selector */}
              <div className="border-b border-af-border/40 p-4">
                <label className="mb-1.5 block text-[10px] uppercase tracking-widest text-af-muted-dim">
                  Agent
                </label>
                <div className="flex flex-col gap-2">
                  {agents.map((a) => {
                    const isSelected = a.id === selectedAgentId;
                    return (
                      <button
                        key={a.id}
                        type="button"
                        onClick={() => setSelectedAgentId(a.id)}
                        className={`flex items-center gap-2.5 rounded-lg border px-3 py-2 text-left transition-all ${
                          isSelected
                            ? "border-af-primary/50 bg-af-primary/10 text-af-primary"
                            : "border-af-border/40 text-af-muted hover:border-af-border hover:text-af-on-surface"
                        }`}
                      >
                        <AgentAvatar name={a.name} />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-xs font-medium">{a.name}</p>
                          {a.description && (
                            <p className="truncate text-[10px] text-af-muted-dim">{a.description}</p>
                          )}
                        </div>
                        {isSelected && (
                          <span className="material-symbols-outlined text-sm text-af-primary">
                            check_circle
                          </span>
                        )}
                      </button>
                    );
                  })}
                  {agents.length === 0 && (
                    <p className="text-xs text-af-muted-dim">No agents available.</p>
                  )}
                </div>
              </div>

              {/* Conversation list header */}
              <div className="flex items-center justify-between border-b border-af-border/40 px-4 py-3">
                <span className="text-[10px] uppercase tracking-widest text-af-muted-dim">
                  Conversations
                </span>
                <button
                  type="button"
                  onClick={() => void handleNewConversation()}
                  disabled={!selectedAgentId}
                  title="New conversation"
                  className="flex h-6 w-6 items-center justify-center rounded-md border border-af-border/60 text-af-muted transition-colors hover:border-af-primary hover:text-af-primary disabled:opacity-40"
                >
                  <span className="material-symbols-outlined text-sm">add</span>
                </button>
              </div>

              {/* Conversation list */}
              <div className="flex-1 overflow-y-auto">
                {conversations.length === 0 && selectedAgentId && (
                  <div className="px-4 py-6 text-center">
                    <span className="material-symbols-outlined mb-2 text-2xl text-af-muted-dim">
                      forum
                    </span>
                    <p className="text-xs text-af-muted-dim">
                      No conversations yet.
                      <br />
                      Start one below.
                    </p>
                  </div>
                )}
                {conversations.map((conv, idx) => {
                  const active = activeConversation?.id === conv.id;
                  return (
                    <div
                      key={conv.id}
                      onClick={() => {
                        setActiveConversation(conv);
                        setMessages([]);
                      }}
                      className={`group flex cursor-pointer flex-col gap-1 border-b border-af-border/20 px-4 py-3 transition-colors ${
                        active
                          ? "bg-af-primary/10 border-l-2 border-l-af-primary"
                          : "hover:bg-white/[0.03]"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="flex-1 truncate text-xs font-medium text-af-on-surface">
                          {conv.title ?? `Conversation #${idx + 1}`}
                        </span>
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
                        <span>{conv.message_count ?? 0} msgs</span>
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

          {/* Collapsed icon pills */}
          {sidebarCollapsed && (
            <div className="flex flex-col items-center gap-2 p-2 pt-3">
              {agents.slice(0, 5).map((a) => {
                const isSelected = a.id === selectedAgentId;
                const initials = a.name
                  .split(" ")
                  .slice(0, 2)
                  .map((w) => w[0]?.toUpperCase() ?? "")
                  .join("");
                return (
                  <button
                    key={a.id}
                    type="button"
                    title={a.name}
                    onClick={() => setSelectedAgentId(a.id)}
                    className={`flex h-8 w-8 items-center justify-center rounded-full border text-xs font-bold transition-all ${
                      isSelected
                        ? "border-af-primary/50 bg-af-primary/20 text-af-primary"
                        : "border-af-border/40 text-af-muted hover:border-af-primary hover:text-af-primary"
                    }`}
                  >
                    {initials || "A"}
                  </button>
                );
              })}
            </div>
          )}
        </aside>

        {/* Main chat area */}
        <div className="flex flex-1 flex-col overflow-hidden bg-af-surface-container/20">
          {/* Header */}
          <div className="flex items-center gap-3 border-b border-af-border/40 px-6 py-3">
            {selectedAgent ? (
              <AgentAvatar name={selectedAgent.name} />
            ) : (
              <div className="flex h-9 w-9 items-center justify-center rounded-full border border-af-border/60 bg-af-surface-high">
                <span className="material-symbols-outlined text-sm text-af-muted">smart_toy</span>
              </div>
            )}
            <div className="flex-1 min-w-0">
              <h1 className="truncate text-sm font-bold text-af-on-surface">
                {activeConversation?.title ??
                  (selectedAgent?.name ?? "Chat")}
              </h1>
              {activeConversation ? (
                <p className="text-[10px] font-mono text-af-muted-dim">
                  thread:{activeConversation.thread_id.slice(0, 8)}…
                  {" · "}
                  {activeConversation.message_count ?? 0} messages
                </p>
              ) : selectedAgent?.description ? (
                <p className="truncate text-[10px] text-af-muted-dim">{selectedAgent.description}</p>
              ) : null}
            </div>
            {activeConversation && (
              <button
                type="button"
                onClick={() => { setActiveConversation(null); setMessages([]); }}
                title="New conversation"
                className="flex items-center gap-1.5 rounded-lg border border-af-border/60 px-3 py-1.5 text-xs text-af-muted transition-colors hover:border-af-primary hover:text-af-primary"
              >
                <span className="material-symbols-outlined text-sm">add</span>
                New
              </button>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-6 py-6">
            {!selectedAgentId && (
              <div className="flex h-full items-center justify-center">
                <div className="text-center">
                  <span className="material-symbols-outlined mb-3 text-4xl text-af-muted-dim">smart_toy</span>
                  <p className="text-sm text-af-muted-dim">Select an agent to start chatting.</p>
                </div>
              </div>
            )}

            {selectedAgentId && messages.length === 0 && !isLoading && (
              <div className="flex h-full flex-col items-center justify-center gap-6 text-center">
                {selectedAgent && <AgentAvatar name={selectedAgent.name} />}
                <div>
                  <p className="text-base font-bold text-af-on-surface">
                    {selectedAgent?.name ?? "Agent"}
                  </p>
                  <p className="mt-1 text-sm text-af-muted">
                    {selectedAgent?.description ?? "Que puis-je faire pour toi ?"}
                  </p>
                </div>
                {/* Suggestion chips */}
                <div className="flex flex-wrap justify-center gap-2 max-w-md">
                  {PROMPT_SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => void handleSend(s)}
                      className="rounded-full border border-af-border/60 bg-af-surface-high px-4 py-2 text-sm text-af-muted transition-colors hover:border-af-primary/60 hover:text-af-primary"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="flex flex-col gap-5">
              {messages.map((msg, idx) => {
                const isUser = msg.role === "user";
                return (
                  <div key={idx} className={`group flex ${isUser ? "justify-end" : "justify-start"}`}>
                    {!isUser && (
                      <div className="mr-3 mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-af-primary/30 bg-af-primary/10">
                        <span className="material-symbols-outlined text-xs text-af-primary">
                          smart_toy
                        </span>
                      </div>
                    )}
                    <div className="flex flex-col gap-1 max-w-[75%]">
                      <div
                        className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                          isUser
                            ? "bg-af-primary text-black"
                            : "border border-af-border/60 bg-af-surface-high text-af-on-surface"
                        }`}
                      >
                        <div className="whitespace-pre-wrap">
                          {msg.content}
                          {msg.streaming && msg.content && (
                            <span className="ml-0.5 inline-block animate-pulse font-bold text-af-primary">
                              ▌
                            </span>
                          )}
                          {msg.streaming && !msg.content && (
                            <span className="flex gap-1.5 py-0.5">
                              <span className="h-2 w-2 animate-bounce rounded-full bg-af-muted [animation-delay:0ms]" />
                              <span className="h-2 w-2 animate-bounce rounded-full bg-af-muted [animation-delay:150ms]" />
                              <span className="h-2 w-2 animate-bounce rounded-full bg-af-muted [animation-delay:300ms]" />
                            </span>
                          )}
                        </div>
                      </div>
                      <span
                        className={`px-1 text-[10px] text-af-muted-dim opacity-0 transition-opacity group-hover:opacity-100 ${
                          isUser ? "text-right" : "text-left"
                        }`}
                      >
                        {timeAgo(msg.timestamp)}
                      </span>
                    </div>
                    {isUser && (
                      <div className="ml-3 mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-af-border/60 bg-af-surface-high text-af-muted">
                        <span className="material-symbols-outlined text-xs">person</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Error */}
            {error && (
              <div className="mt-4 flex items-center gap-2 rounded-lg border border-af-error/30 bg-af-error/10 px-4 py-2 text-xs text-af-error">
                <span className="material-symbols-outlined text-sm">error</span>
                {error}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input area */}
          <div className="border-t border-af-border/40 p-4">
            <div className="flex items-end gap-3 rounded-xl border border-af-border/60 bg-af-surface-high px-4 py-3 focus-within:border-af-primary/60 transition-colors">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  selectedAgentId
                    ? "Message… (Enter to send, Shift+Enter for newline)"
                    : "Select an agent first"
                }
                disabled={!selectedAgentId || isLoading}
                rows={1}
                className="max-h-40 flex-1 resize-none bg-transparent text-sm text-af-on-surface placeholder:text-af-muted-dim focus:outline-none disabled:opacity-50"
                style={{ minHeight: "1.5rem" }}
              />
              <div className="flex shrink-0 items-center gap-2">
                {input.length > 0 && (
                  <span className="text-[10px] text-af-muted-dim">{input.length}</span>
                )}
                <button
                  type="button"
                  onClick={() => void handleSend()}
                  disabled={!input.trim() || !selectedAgentId || isLoading}
                  className="flex h-8 w-8 items-center justify-center rounded-lg bg-af-primary text-black transition-all hover:opacity-90 disabled:opacity-40"
                >
                  {isLoading ? (
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-black border-t-transparent" />
                  ) : (
                    <span className="material-symbols-outlined text-sm">send</span>
                  )}
                </button>
              </div>
            </div>
            <p className="mt-1.5 text-center text-[10px] text-af-muted-dim">
              Conversations are persisted · thread ID ensures multi-turn context
            </p>
          </div>
        </div>
      </div>
    </ToolShell>
  );
}

export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center text-af-muted">
          Loading…
        </div>
      }
    >
      <ChatPageInner />
    </Suspense>
  );
}
