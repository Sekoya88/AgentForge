export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const BASE = API_BASE;

export class ApiError extends Error {
  code?: string;
  requestId?: string;
  constructor(
    message: string,
    public status: number,
    public body?: unknown,
    code?: string,
    requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.requestId = requestId;
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

async function tryRefreshToken(): Promise<boolean> {
  if (typeof window === "undefined") return false;
  const refresh = localStorage.getItem("refresh_token");
  if (!refresh) return false;
  try {
    const res = await fetch(`${BASE}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json() as { access_token?: string; refresh_token?: string };
    if (data.access_token) {
      localStorage.setItem("access_token", data.access_token);
      if (data.refresh_token) localStorage.setItem("refresh_token", data.refresh_token);
      return true;
    }
  } catch { /* */ }
  return false;
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const doFetch = async () => {
    const headers = new Headers(init.headers);
    const ah = authHeaders();
    if (typeof ah === "object" && !Array.isArray(ah)) {
      Object.entries(ah).forEach(([k, v]) => headers.set(k, v));
    }
    if (init.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    return fetch(`${BASE}${path}`, { ...init, headers });
  };

  let res = await doFetch();

  // On 401, attempt one token refresh then retry
  if (res.status === 401) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      res = await doFetch();
    }
  }

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
    const errBody = (typeof data === "object" && data !== null ? data : {}) as Record<string, unknown>;
    const errObj = errBody.error as Record<string, string> | undefined;
    const message = errObj?.message ?? (errBody.detail as string) ?? res.statusText;
    const code = errObj?.code;
    const requestId = errObj?.request_id;
    throw new ApiError(message || res.statusText, res.status, errBody, code, requestId);
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

export function getConversationMessages(agentId: string, convId: string): Promise<{ role: string; content: string }[]> {
  return api<{ role: string; content: string }[]>(`/api/v1/agents/${agentId}/conversations/${convId}/messages`);
}

export function deleteConversation(agentId: string, convId: string): Promise<void> {
  return api<void>(`/api/v1/agents/${agentId}/conversations/${convId}`, {
    method: "DELETE",
  });
}

export interface ExecuteResponse {
  id: string;
  status: string;
  /** Same thread as conversation when client sent thread_id; useful for tracing. */
  thread_id?: string;
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

export type CompareVariantPayload = {
  label: string;
  model_config_override: Record<string, unknown>;
};

export type CompareExecutionRow = {
  id: string;
  status: string;
  compare_group_id?: string | null;
  compare_label?: string | null;
  output_messages: { role: string; content: string }[] | null;
  duration_ms?: number | null;
};

export type AgentCompareResponse = {
  compare_group_id: string;
  executions: CompareExecutionRow[];
};

export function compareAgentExecutions(
  agentId: string,
  message: string,
  variants: CompareVariantPayload[],
  runAsync = false,
): Promise<AgentCompareResponse> {
  return api<AgentCompareResponse>(`/api/v1/agents/${agentId}/compare`, {
    method: "POST",
    body: JSON.stringify({
      message,
      variants,
      run_async: runAsync,
    }),
  });
}

// ── Forge Assistant ───────────────────────────────────────────────────────────

export interface ForgeConversation {
  id: string;
  thread_id: string;
  title: string | null;
  provider: string;
  model: string;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
  message_count: number;
}

export interface ForgeExecuteResponse {
  execution_id: string;
  conversation_id: string;
}

export function forgeListConversations(): Promise<ForgeConversation[]> {
  return api<ForgeConversation[]>("/api/v1/forge/conversations");
}

export function forgeCreateConversation(
  provider = "anthropic",
  model = "claude-sonnet-4-6",
  title?: string,
): Promise<ForgeConversation> {
  return api<ForgeConversation>("/api/v1/forge/conversations", {
    method: "POST",
    body: JSON.stringify({ provider, model, title: title ?? null }),
  });
}

export function forgeGetMessages(convId: string): Promise<{ role: string; content: string }[]> {
  return api<{ role: string; content: string }[]>(`/api/v1/forge/conversations/${convId}/messages`);
}

export function forgeDeleteConversation(convId: string): Promise<void> {
  return api<void>(`/api/v1/forge/conversations/${convId}`, { method: "DELETE" });
}

export function forgeExecute(
  convId: string,
  message: string,
  provider?: string,
  model?: string,
): Promise<ForgeExecuteResponse> {
  return api<ForgeExecuteResponse>(`/api/v1/forge/conversations/${convId}/execute`, {
    method: "POST",
    body: JSON.stringify({ message, provider: provider ?? null, model: model ?? null }),
  });
}
