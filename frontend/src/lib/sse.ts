const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function absoluteUrl(path: string, afterId?: string): string {
  const base = path.startsWith("http") ? path : `${BASE}${path}`;
  if (!afterId) return base;
  const u = new URL(base);
  u.searchParams.set("after_id", afterId);
  return u.toString();
}

/**
 * Single fetch of text/event-stream; returns last seen Redis `id:` field if any.
 */
async function consumeSsePathOnce(
  url: string,
  onLine: (eventName: string, dataJson: string) => void,
  signal?: AbortSignal,
): Promise<string | undefined> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal,
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || res.statusText);
  }
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");
  const dec = new TextDecoder();
  let buf = "";
  let currentEvent = "message";
  let lastStreamId: string | undefined;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let dataLine = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("id:")) lastStreamId = line.slice(3).trim();
        else if (line.startsWith("event:")) currentEvent = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLine = line.slice(5).trim();
        else if (line.startsWith(":")) continue;
      }
      if (dataLine) onLine(currentEvent, dataLine);
      currentEvent = "message";
    }
  }
  return lastStreamId;
}

export type ConsumeSseRetryOpts = {
  maxRetries?: number;
  baseDelayMs?: number;
  signal?: AbortSignal;
};

/**
 * SSE with exponential backoff reconnect; passes `after_id` when the server emitted `id:` lines.
 */
export async function consumeSsePathWithRetry(
  path: string,
  onLine: (eventName: string, dataJson: string) => void,
  opts?: ConsumeSseRetryOpts,
): Promise<void> {
  const maxRetries = opts?.maxRetries ?? 5;
  const baseDelayMs = opts?.baseDelayMs ?? 500;
  let attempt = 0;
  let afterId: string | undefined;
  while (attempt <= maxRetries) {
    try {
      const url = absoluteUrl(path, afterId);
      const last = await consumeSsePathOnce(url, onLine, opts?.signal);
      if (last) afterId = last;
      return;
    } catch {
      attempt += 1;
      if (attempt > maxRetries) break;
      const delay = baseDelayMs * 2 ** (attempt - 1);
      await new Promise((r) => setTimeout(r, delay));
    }
  }
  throw new Error("SSE: max retries exceeded");
}

/**
 * Consume text/event-stream with Authorization header (EventSource cannot).
 * Uses bounded reconnect with `after_id` when stream ids are present.
 */
export async function consumeSsePath(
  path: string,
  onLine: (eventName: string, dataJson: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  return consumeSsePathWithRetry(path, onLine, { signal });
}

export function consumeExecutionSse(
  agentId: string,
  executionId: string,
  onLine: (eventName: string, dataJson: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  return consumeSsePath(`/api/v1/agents/${agentId}/stream/${executionId}`, onLine, signal);
}

export function consumeForgeSse(
  executionId: string,
  onLine: (eventName: string, dataJson: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  return consumeSsePath(`/api/v1/forge/stream/${executionId}`, onLine, signal);
}

export function consumeFinetuneSse(
  jobId: string,
  onLine: (eventName: string, dataJson: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  return consumeSsePath(`/api/v1/finetune/${jobId}/stream`, onLine, signal);
}
