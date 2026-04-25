"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import {
  API_BASE,
  ApiError,
  Conversation,
  api,
  buildAuthHeaders,
  createConversation,
  deleteConversation,
  executeAgent,
  listConversations,
  getConversationMessages,
} from "@/lib/api";
import { consumeExecutionSse } from "@/lib/sse";
import { ChatMessage } from "@/types/chat";
import { MarkdownMessage } from "@/components/chat/MarkdownMessage";
import { useAgentActivity } from "@/hooks/useAgentActivity";
import { AgentToastStack } from "@/components/agent/AgentToastStack";
import { AgentStepChips } from "@/components/agent/AgentStepChips";

type Agent = {
  id: string;
  name: string;
  status: string;
  description: string | null;
  graph_definition?: { nodes?: { type?: string }[] } | null;
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
  "Résume tes capacités en 3 points.",
  "Donne-moi un exemple d'usage concret.",
  "Quelles sont tes limites ?",
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

  const { activity, onLine: activityOnLine, reset: resetActivity, stepsRef } = useAgentActivity();

  // ── Voice recording state ────────────────────────────────────────────────
  const [voiceRecording, setVoiceRecording] = useState(false);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const voiceRecorderRef = useRef<MediaRecorder | null>(null);
  const voiceChunksRef = useRef<Blob[]>([]);
  const voiceAudioRef = useRef<HTMLAudioElement | null>(null);

  // computed after agents state is set (selectedAgent derived below, so we use agents here)
  const isVoiceAgent = !!(
    agents
      .find((a) => a.id === selectedAgentId)
      ?.graph_definition?.nodes?.some((n) => n.type === "asr" || n.type === "tts")
  );

  async function startVoiceRecording() {
    setVoiceError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      voiceRecorderRef.current = recorder;
      voiceChunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) voiceChunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        void sendVoiceRecording();
      };
      recorder.start();
      setVoiceRecording(true);
    } catch (e) {
      setVoiceError(e instanceof Error ? e.message : "Microphone access denied");
    }
  }

  function stopVoiceRecording() {
    voiceRecorderRef.current?.stop();
    setVoiceRecording(false);
  }

  async function sendVoiceRecording() {
    if (!selectedAgentId) return;
    setVoiceBusy(true);
    const now = Date.now();

    // Add a placeholder user message while processing
    setMessages((prev) => [
      ...prev,
      { role: "user" as const, content: "🎤 …", timestamp: now },
      { role: "assistant" as const, content: "", streaming: true, timestamp: now + 1 },
    ]);

    try {
      const blob = new Blob(voiceChunksRef.current, { type: "audio/webm" });
      const form = new FormData();
      form.append("file", blob, "recording.webm");
      form.append("input_messages", JSON.stringify([{ role: "user", content: "" }]));

      const res = await fetch(
        `${API_BASE}/api/v1/agents/${selectedAgentId}/execute/audio`,
        { method: "POST", headers: buildAuthHeaders(), body: form },
      );
      const body = await res.json() as {
        status?: string;
        output_audio_b64?: string | null;
        output_messages?: { role: string; content: string }[] | null;
      };

      const msgs = body.output_messages ?? [];
      const userMsg = msgs.find((m) => m.role === "user");
      const aiMsg = [...msgs].reverse().find((m) => m.role === "assistant");
      const transcript = typeof userMsg?.content === "string" && userMsg.content ? userMsg.content : "🎤 (audio)";
      const reply = typeof aiMsg?.content === "string" ? aiMsg.content : "(no response)";
      const audioB64 = body.output_audio_b64 ?? null;

      setMessages((prev) => {
        const next = [...prev];
        // Replace the last two placeholders
        if (next.length >= 2) {
          next[next.length - 2] = { role: "user", content: transcript, timestamp: now };
          next[next.length - 1] = { role: "assistant", content: reply, streaming: false, timestamp: now + 1, audioB64 };
        }
        return next;
      });

      // Auto-play audio response
      if (audioB64) {
        voiceAudioRef.current?.pause();
        const audio = new Audio(`data:audio/mp3;base64,${audioB64}`);
        voiceAudioRef.current = audio;
        void audio.play().catch(() => { /* user gesture required in some browsers */ });
      }
    } catch (e) {
      setVoiceError(e instanceof Error ? e.message : "Voice send failed");
      setMessages((prev) => prev.filter((m) => !(m.streaming && m.content === "")));
    } finally {
      setVoiceBusy(false);
      voiceRecorderRef.current = null;
      voiceChunksRef.current = [];
    }
  }

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

  // Load conversations + full agent details (graph_definition) when agent changes
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
        const [convs, fullAgent] = await Promise.all([
          listConversations(selectedAgentId),
          api<Agent>(`/api/v1/agents/${selectedAgentId}`),
        ]);
        if (!cancelled) {
          setConversations(convs);
          setActiveConversation(null);
          setMessages([]);
          // Merge graph_definition into the agents list
          setAgents((prev) =>
            prev.map((a) => (a.id === selectedAgentId ? { ...a, ...fullAgent } : a)),
          );
        }
      } catch {
        if (!cancelled) setConversations([]);
      }
    })();
    return () => { cancelled = true; };
  }, [selectedAgentId]);

  // Load messages when activeConversation changes
  useEffect(() => {
    if (!selectedAgentId || !activeConversation) return;
    let cancelled = false;
    (async () => {
      try {
        const msgs = await getConversationMessages(selectedAgentId, activeConversation.id);
        if (!cancelled) {
          setMessages(
            msgs.map((m, i) => ({
              role: m.role as "user" | "assistant",
              content: m.content,
              timestamp: Date.now() - (msgs.length - i) * 1000,
            }))
          );
        }
      } catch (e) {
        console.error("Failed to load messages:", e);
      }
    })();
    return () => { cancelled = true; };
  }, [selectedAgentId, activeConversation]);

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
        const failed = exec.status === "failed" || !assistantContent;
        setMessages((prev) =>
          prev.map((m, i) =>
            i === prev.length - 1
              ? { role: "assistant", content: assistantContent, failed, timestamp: Date.now() }
              : m,
          ),
        );
      } else {
        let accumulated = "";
        resetActivity();
        await consumeExecutionSse(
          selectedAgentId,
          exec.id,
          (event, dataJson) => {
            activityOnLine(event, dataJson);
            if (event === "token") {
              try {
                const parsed = JSON.parse(dataJson);
                const token = parsed?.text ?? parsed?.token ?? parsed?.content ?? dataJson;
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
                  i === prev.length - 1 ? { ...m, streaming: false, steps: stepsRef.current } : m,
                ),
              );
            }
          },
          signal,
        );

        try {
          const final = await api<{
            status?: string;
            output_messages: { role: string; content: string }[] | null;
          }>(`/api/v1/agents/${selectedAgentId}/executions/${exec.id}`);
          const finalContent =
            final.output_messages?.filter((m) => m.role === "assistant").pop()?.content ??
            accumulated;
          const failed = final.status === "failed" || !finalContent;
          setMessages((prev) =>
            prev.map((m, i) =>
              i === prev.length - 1
                ? { role: "assistant", content: finalContent, failed, streaming: false, steps: stepsRef.current, timestamp: m.timestamp }
                : m,
            ),
          );
        } catch {
          const failed = !accumulated;
          setMessages((prev) =>
            prev.map((m, i) =>
              i === prev.length - 1
                ? { role: "assistant", content: accumulated, failed, streaming: false, steps: stepsRef.current, timestamp: m.timestamp }
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
  }, [input, selectedAgentId, activeConversation, isLoading, activityOnLine, resetActivity, stepsRef]);

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
            <div className="flex items-center gap-2">
              {selectedAgent && (
                <Link
                  href={`https://cloud.langfuse.com/project/agentforge/traces?tags=agent:${selectedAgent.id}`}
                  target="_blank"
                  className="flex items-center gap-1 rounded bg-af-surface-container/30 px-2 py-1 text-[10px] font-bold text-af-primary transition-colors hover:bg-af-primary/20"
                >
                  <span className="material-symbols-outlined text-[12px]">analytics</span>
                  LANGFUSE
                </Link>
              )}
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
                <div className="flex flex-col">
                  <p className="text-base font-bold text-af-on-surface">
                    {selectedAgent?.name ?? "Agent"}
                  </p>
                  <p className="mt-1 text-sm text-af-muted">
                    {selectedAgent?.description ?? "Que puis-je faire pour toi ?"}
                  </p>
                </div>
                {/* Suggestion chips */}
                <div className="flex max-w-md flex-wrap justify-center gap-2">
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
                            <span className="italic text-af-error">Une erreur est survenue. Veuillez réessayer.</span>
                          ) : isUser ? (
                            <span className="whitespace-pre-wrap">{msg.content}</span>
                          ) : (
                            <>
                              {msg.streaming && !msg.content ? (
                                <div className="flex flex-col gap-3">
                                  <div className="max-w-[400px]">
                                    <AgentToastStack
                                      toasts={activity.toasts}
                                      isRunning={activity.isRunning}
                                      inline={true}
                                    />
                                  </div>
                                </div>
                              ) : (
                                msg.content && (
                                  <MarkdownMessage content={msg.content} className="prose-invert text-sm leading-relaxed" />
                                )
                              )}
                              {msg.streaming && msg.content && (
                                <span className="ml-0.5 inline-block animate-pulse font-bold text-af-primary">▌</span>
                              )}
                              {msg.audioB64 && !msg.streaming && (
                                <audio
                                  controls
                                  src={`data:audio/mp3;base64,${msg.audioB64}`}
                                  className="mt-2 h-7 w-full max-w-xs"
                                  preload="metadata"
                                />
                              )}
                           </>
                         )}
                       </div>
                        {msg.steps && msg.steps.length > 0 && (
                          <div className="mt-2 border-t border-af-border/40 pt-2">
                            <AgentStepChips steps={msg.steps} />
                          </div>
                        )}
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
                      <div className="ml-2 mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-af-border/60 bg-af-surface-high text-af-muted">
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
            {/* Voice recording banner */}
            {voiceRecording && (
              <div className="mb-2 flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2">
                <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-red-400" />
                <span className="flex-1 text-xs text-red-300">Enregistrement… Appuie sur le micro pour envoyer.</span>
                <div className="flex items-end gap-0.5" style={{ height: "1.2rem" }}>
                  {[0.4,0.8,1,0.6,0.9].map((h, i) => (
                    <div key={i} className="w-0.5 rounded-full bg-red-400"
                      style={{ height: `${h*100}%`, animation: "wavebar 0.7s ease-in-out infinite alternate", animationDelay: `${i*100}ms` }} />
                  ))}
                  <style>{`@keyframes wavebar{from{transform:scaleY(0.3)}to{transform:scaleY(1)}}`}</style>
                </div>
              </div>
            )}
            {voiceError && (
              <p className="mb-2 text-xs text-af-error">{voiceError}</p>
            )}
            <div className={`flex items-end gap-3 rounded-xl border bg-af-surface-high px-4 py-3 focus-within:border-af-primary/60 transition-colors ${voiceRecording ? "border-red-500/50" : "border-af-border/60"}`}>
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  voiceRecording ? "Écoute en cours…"
                  : selectedAgentId
                    ? "Message… (Enter to send, Shift+Enter for newline)"
                    : "Select an agent first"
                }
                disabled={!selectedAgentId || isLoading || voiceRecording || voiceBusy}
                rows={1}
                className="max-h-40 flex-1 resize-none bg-transparent text-sm text-af-on-surface placeholder:text-af-muted-dim focus:outline-none disabled:opacity-50"
                style={{ minHeight: "1.5rem" }}
              />
              <div className="flex shrink-0 items-center gap-2">
                {input.length > 0 && !voiceRecording && (
                  <span className="text-[10px] text-af-muted-dim">{input.length}</span>
                )}
                {/* Mic button — only for voice agents */}
                {isVoiceAgent && selectedAgentId && (
                  <button
                    type="button"
                    disabled={isLoading || voiceBusy}
                    onClick={() => {
                      if (voiceRecording) stopVoiceRecording();
                      else void startVoiceRecording();
                    }}
                    title={voiceRecording ? "Stop & envoyer" : "Parler à l'agent"}
                    className={`flex h-8 w-8 items-center justify-center rounded-lg border transition-all disabled:opacity-40 ${
                      voiceRecording
                        ? "border-red-500 bg-red-500 text-white shadow-[0_0_12px_rgba(239,68,68,0.4)]"
                        : "border-af-border/60 text-af-muted hover:border-af-primary/60 hover:text-af-primary"
                    }`}
                  >
                    {voiceBusy ? (
                      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    ) : (
                      <span className="material-symbols-outlined text-sm">
                        {voiceRecording ? "stop" : "mic"}
                      </span>
                    )}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => void handleSend()}
                  disabled={!input.trim() || !selectedAgentId || isLoading || voiceRecording || voiceBusy}
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
              {isVoiceAgent && " · 🎤 Voice mode disponible"}
            </p>
          {/* Loading activities inline in bubbles now */}
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
