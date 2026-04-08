/**
 * useCollabPresence — real-time cursor presence for the agent builder.
 *
 * Connects to WS /api/v1/collab/agents/{agentId}?token=<jwt>
 * and broadcasts cursor position + node selection.
 *
 * Usage:
 *   const { peers, sendCursor, sendSelection } = useCollabPresence(agentId);
 */

import { useCallback, useEffect, useRef, useState } from "react";

export type PeerCursor = {
  user_id: string;
  display_name: string;
  x: number;
  y: number;
  node_id: string | null;
};

type CollabMessage =
  | { type: "presence"; users: PeerCursor[] }
  | { type: "joined"; user_id: string; display_name: string }
  | { type: "left"; user_id: string }
  | { type: "cursor"; user_id: string; display_name: string; x: number; y: number; node_id: string | null }
  | { type: "selection"; user_id: string; node_id: string | null }
  | { type: "pong" };

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem("access_token");
  } catch {
    return null;
  }
}

function getWsBase(): string {
  if (typeof window === "undefined") return "";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  // In dev, backend is on :8000; in prod the proxy handles it
  const host = process.env.NEXT_PUBLIC_API_HOST ?? window.location.host.replace("3000", "8000");
  return `${proto}//${host}`;
}

export function useCollabPresence(agentId: string | null) {
  const [peers, setPeers] = useState<PeerCursor[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!agentId) return;
    const token = getToken();
    if (!token) return;

    const url = `${getWsBase()}/api/v1/collab/agents/${agentId}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (evt) => {
      let msg: CollabMessage;
      try {
        msg = JSON.parse(evt.data) as CollabMessage;
      } catch {
        return;
      }

      switch (msg.type) {
        case "presence":
          setPeers(msg.users);
          break;

        case "joined":
          // Add peer with zero position until we get a cursor update
          setPeers((prev) => {
            if (prev.find((p) => p.user_id === msg.user_id)) return prev;
            return [...prev, { user_id: msg.user_id, display_name: msg.display_name, x: 0, y: 0, node_id: null }];
          });
          break;

        case "left":
          setPeers((prev) => prev.filter((p) => p.user_id !== msg.user_id));
          break;

        case "cursor":
          setPeers((prev) =>
            prev.map((p) =>
              p.user_id === msg.user_id
                ? { ...p, x: msg.x, y: msg.y, node_id: msg.node_id }
                : p,
            ),
          );
          break;

        case "selection":
          setPeers((prev) =>
            prev.map((p) =>
              p.user_id === msg.user_id ? { ...p, node_id: msg.node_id } : p,
            ),
          );
          break;
      }
    };

    ws.onclose = () => setPeers([]);

    // Keepalive ping every 20 s
    pingRef.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 20_000);

    return () => {
      if (pingRef.current) clearInterval(pingRef.current);
      ws.close();
      wsRef.current = null;
    };
  }, [agentId]);

  const sendCursor = useCallback((x: number, y: number) => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "cursor", x, y }));
    }
  }, []);

  const sendSelection = useCallback((nodeId: string | null) => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "selection", node_id: nodeId }));
    }
  }, []);

  return { peers, sendCursor, sendSelection };
}
