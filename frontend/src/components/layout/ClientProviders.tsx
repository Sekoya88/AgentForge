"use client";

import { ChatProvider } from "@/contexts/ChatContext";
import { ChatSlideOver } from "@/components/chat/ChatSlideOver";
import { FloatingChatButton } from "@/components/chat/FloatingChatButton";

export function ClientProviders({ children }: { children: React.ReactNode }) {
  return (
    <ChatProvider>
      {children}
      <FloatingChatButton />
      <ChatSlideOver />
    </ChatProvider>
  );
}
