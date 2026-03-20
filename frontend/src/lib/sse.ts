const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Consume text/event-stream with Authorization header (EventSource cannot).
 */
export async function consumeSsePath(
  path: string,
  onLine: (eventName: string, dataJson: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const url = path.startsWith("http") ? path : `${BASE}${path}`;
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
        if (line.startsWith("event:")) currentEvent = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLine = line.slice(5).trim();
        else if (line.startsWith(":")) continue;
      }
      if (dataLine) onLine(currentEvent, dataLine);
      currentEvent = "message";
    }
  }
}

export function consumeExecutionSse(
  agentId: string,
  executionId: string,
  onLine: (eventName: string, dataJson: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  return consumeSsePath(`/api/v1/agents/${agentId}/stream/${executionId}`, onLine, signal);
}
