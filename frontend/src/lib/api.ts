export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const BASE = API_BASE;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function authHeaders(): HeadersInit {
  if (typeof window === "undefined") return {};
  const t = localStorage.getItem("access_token");
  return t ? { Authorization: `Bearer ${t}` } : {};
}

/** Headers with Bearer token; use for multipart fetch (do not set Content-Type). */
export function buildAuthHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init);
  if (typeof window !== "undefined") {
    const t = localStorage.getItem("access_token");
    if (t) headers.set("Authorization", `Bearer ${t}`);
  }
  return headers;
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  const ah = authHeaders();
  if (typeof ah === "object" && !Array.isArray(ah)) {
    Object.entries(ah).forEach(([k, v]) => headers.set(k, v));
  }
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const detail =
      typeof data === "object" && data !== null && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : text;
    throw new ApiError(detail || res.statusText, res.status, data);
  }
  return data as T;
}

function notifyAuthChanged() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent("af-auth-changed"));
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
  notifyAuthChanged();
}

export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  notifyAuthChanged();
}

// ── Conversation types & helpers ──────────────────────────────────────────────

export interface Conversation {
  id: string;
  agent_id: string;
  thread_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
  message_count: number;
}

export function createConversation(agentId: string, title?: string): Promise<Conversation> {
  return api<Conversation>(`/api/v1/agents/${agentId}/conversations`, {
    method: "POST",
    body: JSON.stringify({ title: title ?? null }),
  });
}

export function listConversations(agentId: string): Promise<Conversation[]> {
  return api<Conversation[]>(`/api/v1/agents/${agentId}/conversations`);
}

export function deleteConversation(agentId: string, convId: string): Promise<void> {
  return api<void>(`/api/v1/agents/${agentId}/conversations/${convId}`, {
    method: "DELETE",
  });
}

export interface ExecuteResponse {
  id: string;
  status: string;
  output_messages: { role: string; content: string }[] | null;
  duration_ms: number | null;
}

export function executeAgent(
  agentId: string,
  message: string,
  threadId?: string,
  runAsync = false,
): Promise<ExecuteResponse> {
  return api<ExecuteResponse>(`/api/v1/agents/${agentId}/execute`, {
    method: "POST",
    body: JSON.stringify({
      input_messages: [{ role: "user", content: message }],
      run_async: runAsync,
      thread_id: threadId ?? null,
    }),
  });
}
