"use client";

import { createContext, useCallback, useContext, useState } from "react";

interface ChatContextType {
  isOpen: boolean;
  selectedAgentId: string | null;
  openChat: (agentId?: string) => void;
  closeChat: () => void;
  setSelectedAgentId: (id: string | null) => void;
}

const ChatContext = createContext<ChatContextType | null>(null);

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

  const openChat = useCallback((agentId?: string) => {
    if (agentId) setSelectedAgentId(agentId);
    setIsOpen(true);
  }, []);

  const closeChat = useCallback(() => {
    setIsOpen(false);
  }, []);

  return (
    <ChatContext.Provider value={{ isOpen, selectedAgentId, openChat, closeChat, setSelectedAgentId }}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChatContext() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChatContext must be used inside ChatProvider");
  return ctx;
}
