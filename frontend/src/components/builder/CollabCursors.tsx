"use client";

/**
 * CollabCursors — renders peer cursor overlays inside the builder canvas.
 *
 * Usage (inside the builder page/canvas):
 *   const { peers, sendCursor, sendSelection } = useCollabPresence(agentId);
 *   <CollabCursors peers={peers} />
 *
 * Wire up `sendCursor` to the canvas onMouseMove event.
 */

import type { PeerCursor } from "@/hooks/useCollabPresence";

const COLORS = [
  "#f43f5e", // rose
  "#8b5cf6", // violet
  "#06b6d4", // cyan
  "#f59e0b", // amber
  "#10b981", // emerald
  "#ec4899", // pink
];

function colorForUser(userId: string) {
  let hash = 0;
  for (let i = 0; i < userId.length; i++) {
    hash = (hash * 31 + userId.charCodeAt(i)) >>> 0;
  }
  return COLORS[hash % COLORS.length];
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

type Props = {
  peers: PeerCursor[];
  /** If provided, only show peers whose node_id matches a selected node */
  highlightNodeId?: string | null;
};

export function CollabCursors({ peers, highlightNodeId }: Props) {
  if (peers.length === 0) return null;

  return (
    <>
      {peers.map((peer) => {
        const color = colorForUser(peer.user_id);
        const isOnNode = highlightNodeId && peer.node_id === highlightNodeId;

        return (
          <div
            key={peer.user_id}
            className="pointer-events-none absolute z-50 transition-transform duration-100"
            style={{ left: peer.x, top: peer.y, transform: "translate(-2px, -2px)" }}
          >
            {/* SVG cursor */}
            <svg width="16" height="20" viewBox="0 0 16 20" fill="none">
              <path
                d="M0 0L0 14L4 11L6 16L8 15L6 10H10L0 0Z"
                fill={color}
                stroke="white"
                strokeWidth="1"
              />
            </svg>

            {/* Name tag */}
            <div
              className="absolute left-3 top-4 whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-bold text-white shadow-lg"
              style={{ backgroundColor: color }}
            >
              {peer.display_name || initials(peer.user_id)}
            </div>

            {/* Node selection indicator */}
            {isOnNode && (
              <div
                className="absolute -top-1 -left-1 h-2 w-2 rounded-full animate-ping"
                style={{ backgroundColor: color }}
              />
            )}
          </div>
        );
      })}

      {/* Presence avatars strip (top-right corner, positioned by parent) */}
      <div className="pointer-events-none absolute right-4 top-4 flex -space-x-2 z-40">
        {peers.slice(0, 6).map((peer) => {
          const color = colorForUser(peer.user_id);
          return (
            <div
              key={peer.user_id}
              title={peer.display_name}
              className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-af-surface text-[10px] font-bold text-white shadow"
              style={{ backgroundColor: color }}
            >
              {initials(peer.display_name || peer.user_id)}
            </div>
          );
        })}
        {peers.length > 6 && (
          <div className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-af-surface bg-af-surface-high text-[10px] text-af-muted shadow">
            +{peers.length - 6}
          </div>
        )}
      </div>
    </>
  );
}
