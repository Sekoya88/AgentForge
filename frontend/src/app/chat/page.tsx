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
};

function formatDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
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
          // Pre-select from ?agent= query param
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
    return () => {
      cancelled = true;
    };
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
    return () => {
      cancelled = true;
    };
  }, [selectedAgentId]);

  const handleNewConversation = useCallback(async () => {
    if (!selectedAgentId) return;
    try {
      const conv = await createConversation(selectedAgentId);
      setConversations((prev) => [conv, ...prev]);
      setActiveConversation(conv);
      setMessages([]);
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

  const handleSend = useCallback(async () => {
    if (!input.trim() || !selectedAgentId || isLoading) return;

    const userMsg = input.trim();
    setInput("");
    setError(null);

    // If no active conversation, create one first
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

    // Append user message immediately
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    // Placeholder assistant message with streaming cursor
    setMessages((prev) => [...prev, { role: "assistant", content: "", streaming: true }]);
    setIsLoading(true);

    abortRef.current?.abort();
    abortRef.current = new AbortController();
    const signal = abortRef.current.signal;

    try {
      // Use streaming (run_async=true) + SSE
      const exec = await executeAgent(selectedAgentId, userMsg, conv.thread_id, true);

      if (exec.status !== "running") {
        // Synchronous result
        const assistantContent =
          exec.output_messages?.find((m) => m.role === "assistant")?.content ?? "";
        setMessages((prev) =>
          prev.map((m, i) =>
            i === prev.length - 1 ? { role: "assistant", content: assistantContent } : m,
          ),
        );
      } else {
        // Stream SSE
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
                setMessages((prev) =>
                  prev.map((m, i) =>
                    i === prev.length - 1
                      ? { role: "assistant", content: accumulated, streaming: true }
                      : m,
                  ),
                );
              } catch {
                accumulated += dataJson;
                setMessages((prev) =>
                  prev.map((m, i) =>
                    i === prev.length - 1
                      ? { role: "assistant", content: accumulated, streaming: true }
                      : m,
                  ),
                );
              }
            } else if (event === "done" || event === "completed") {
              // Final — stop streaming cursor
              setMessages((prev) =>
                prev.map((m, i) =>
                  i === prev.length - 1 ? { ...m, streaming: false } : m,
                ),
              );
            }
          },
          signal,
        );

        // Fetch final result to ensure we have complete output
        try {
          const final = await api<{
            output_messages: { role: string; content: string }[] | null;
          }>(`/api/v1/agents/${selectedAgentId}/executions/${exec.id}`);
          const finalContent =
            final.output_messages?.filter((m) => m.role === "assistant").pop()?.content ??
            accumulated;
          setMessages((prev) =>
            prev.map((m, i) =>
              i === prev.length - 1 ? { role: "assistant", content: finalContent } : m,
            ),
          );
        } catch {
          // Keep accumulated content if fetch fails
          setMessages((prev) =>
            prev.map((m, i) =>
              i === prev.length - 1
                ? { role: "assistant", content: accumulated, streaming: false }
                : m,
            ),
          );
        }
      }

      // Refresh conversation list to update last_message_at / message_count
      try {
        const convs = await listConversations(selectedAgentId);
        setConversations(convs);
      } catch {
        /* non-critical */
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setError(e instanceof Error ? e.message : "Execute failed");
      // Remove the streaming placeholder on error
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

  return (
    <ToolShell active="chat">
      <div className="flex h-[calc(100vh-4rem-2rem)] gap-0 overflow-hidden rounded-xl border border-af-border/40">
        {/* Sidebar */}
        <aside className="flex w-72 shrink-0 flex-col border-r border-af-border/40 bg-af-surface-container/60">
          {/* Agent selector */}
          <div className="border-b border-af-border/40 p-4">
            <label className="mb-1.5 block text-[10px] uppercase tracking-widest text-af-muted-dim">
              Agent
            </label>
            <select
              value={selectedAgentId ?? ""}
              onChange={(e) => setSelectedAgentId(e.target.value || null)}
              className="w-full rounded-lg border border-af-border/60 bg-af-surface-high px-3 py-2 text-sm text-af-on-surface focus:border-af-primary focus:outline-none"
            >
              {agents.length === 0 && <option value="">No agents</option>}
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
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
              <div className="px-4 py-6 text-center text-xs text-af-muted-dim">
                No conversations yet.
                <br />
                Start a new one above.
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
                    <span className="flex-1 truncate text-sm font-medium text-af-on-surface">
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
                        <span>{formatDate(conv.last_message_at)}</span>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </aside>

        {/* Main chat area */}
        <div className="flex flex-1 flex-col overflow-hidden bg-af-surface-container/20">
          {/* Header */}
          <div className="flex items-center gap-3 border-b border-af-border/40 px-6 py-4">
            <span className="material-symbols-outlined text-af-primary">chat</span>
            <div>
              <h1 className="text-sm font-bold text-af-on-surface">
                {activeConversation?.title ??
                  (selectedAgentId
                    ? agents.find((a) => a.id === selectedAgentId)?.name ?? "Chat"
                    : "Chat")}
              </h1>
              {activeConversation && (
                <p className="text-[10px] text-af-muted-dim">
                  thread: {activeConversation.thread_id.slice(0, 8)}…
                </p>
              )}
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-6 py-6">
            {!selectedAgentId && (
              <div className="flex h-full items-center justify-center">
                <p className="text-sm text-af-muted-dim">Select an agent to start chatting.</p>
              </div>
            )}

            {selectedAgentId && messages.length === 0 && !isLoading && (
              <div className="flex h-full flex-col items-center justify-center gap-4">
                <div className="flex h-16 w-16 items-center justify-center rounded-full border border-af-border/60 bg-af-surface-high text-af-primary">
                  <span className="material-symbols-outlined text-3xl">smart_toy</span>
                </div>
                <p className="text-sm text-af-muted">
                  {activeConversation
                    ? "Continue your conversation below."
                    : "Send a message to start a new conversation."}
                </p>
              </div>
            )}

            <div className="flex flex-col gap-4">
              {messages.map((msg, idx) => {
                const isUser = msg.role === "user";
                return (
                  <div key={idx} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                    {!isUser && (
                      <div className="mr-2 mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-af-border/60 bg-af-surface-high text-af-primary">
                        <span className="material-symbols-outlined text-sm">smart_toy</span>
                      </div>
                    )}
                    <div
                      className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                        isUser
                          ? "bg-af-primary text-black"
                          : "border border-af-border/60 bg-af-surface-high text-af-on-surface"
                      }`}
                    >
                      <div className="whitespace-pre-wrap">
                        {msg.content}
                        {msg.streaming && (
                          <span className="ml-0.5 inline-block animate-pulse font-bold text-af-primary">
                            |
                          </span>
                        )}
                      </div>
                    </div>
                    {isUser && (
                      <div className="ml-2 mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-af-border/60 bg-af-surface-high text-af-muted">
                        <span className="material-symbols-outlined text-sm">person</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Error */}
            {error && (
              <div className="mt-4 rounded-lg border border-af-error/30 bg-af-error/10 px-4 py-2 text-xs text-af-error">
                {error}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input area */}
          <div className="border-t border-af-border/40 p-4">
            <div className="flex items-end gap-3 rounded-xl border border-af-border/60 bg-af-surface-high px-4 py-3 focus-within:border-af-primary/60">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  selectedAgentId ? "Message… (Enter to send, Shift+Enter for newline)" : "Select an agent first"
                }
                disabled={!selectedAgentId || isLoading}
                rows={1}
                className="max-h-40 flex-1 resize-none bg-transparent text-sm text-af-on-surface placeholder:text-af-muted-dim focus:outline-none disabled:opacity-50"
                style={{ minHeight: "1.5rem" }}
              />
              <button
                type="button"
                onClick={() => void handleSend()}
                disabled={!input.trim() || !selectedAgentId || isLoading}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-af-primary text-black transition-all hover:opacity-90 disabled:opacity-40"
              >
                {isLoading ? (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-black border-t-transparent" />
                ) : (
                  <span className="material-symbols-outlined text-sm">send</span>
                )}
              </button>
            </div>
            <p className="mt-1.5 text-center text-[10px] text-af-muted-dim">
              Conversations are persisted with a thread ID for multi-turn context.
            </p>
          </div>
        </div>
      </div>
    </ToolShell>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-af-muted">Loading…</div>}>
      <ChatPageInner />
    </Suspense>
  );
}
