"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import { useChatContext } from "@/contexts/ChatContext";

type AgentMini = { id: string; name: string };

export function FloatingChatButton() {
  const pathname = usePathname();
  const { isOpen, selectedAgentId, openChat } = useChatContext();
  const [agentName, setAgentName] = useState<string | null>(null);

  // Don't show on /chat page (it has its own full UI)
  if (pathname === "/chat") return null;

  // eslint-disable-next-line react-hooks/rules-of-hooks
  useEffect(() => {
    if (!selectedAgentId) {
      setAgentName(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const agent = await api<AgentMini>(`/api/v1/agents/${selectedAgentId}`);
        if (!cancelled) setAgentName(agent.name);
      } catch {
        /* ignore */
      }
    })();
    return () => { cancelled = true; };
  }, [selectedAgentId]);

  if (isOpen) return null;

  return (
    <button
      type="button"
      onClick={() => openChat()}
      aria-label="Open chat"
      className="fixed bottom-6 right-6 z-40 flex items-center gap-2 rounded-full border border-af-primary/30 bg-af-primary px-4 py-3 text-sm font-bold text-black shadow-[0_0_24px_rgba(195,192,255,0.25)] transition-all hover:scale-105 hover:shadow-[0_0_32px_rgba(195,192,255,0.4)] active:scale-95"
    >
      {/* Pulse ring */}
      <span className="relative flex h-2 w-2 shrink-0">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-black opacity-40" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-black/70" />
      </span>
      <span className="material-symbols-outlined text-base leading-none">chat</span>
      <span className="max-w-[120px] truncate">
        {agentName ?? "Chat"}
      </span>
    </button>
  );
}
