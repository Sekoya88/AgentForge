"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

const STORAGE_KEY = "af_last_chat_agent_id";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

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
  const [selectedAgentId, setSelectedAgentIdState] = useState<string | null>(null);

  // Initialize from LocalStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && UUID_RE.test(saved)) setSelectedAgentIdState(saved);
    } catch {
      /* ignore */
    }
  }, []);

  const setSelectedAgentId = useCallback((id: string | null) => {
    setSelectedAgentIdState(id);
    try {
      if (id) localStorage.setItem(STORAGE_KEY, id);
      else localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore quota / private mode */
    }
  }, []);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw && UUID_RE.test(raw)) setSelectedAgentIdState(raw);
    } catch {
      /* ignore */
    }
  }, []);

  const openChat = useCallback(
    (agentId?: string) => {
      if (agentId) setSelectedAgentId(agentId);
      setIsOpen(true);
    },
    [setSelectedAgentId],
  );

  const closeChat = useCallback(() => {
    setIsOpen(false);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== "j") return;
      const t = e.target as HTMLElement | null;
      if (
        t &&
        (t.tagName === "INPUT" ||
          t.tagName === "TEXTAREA" ||
          t.isContentEditable)
      ) {
        return;
      }
      e.preventDefault();
      setIsOpen((o) => !o);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <ChatContext.Provider
      value={{
        isOpen,
        selectedAgentId,
        openChat,
        closeChat,
        setSelectedAgentId,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChatContext() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChatContext must be used inside ChatProvider");
  return ctx;
}
