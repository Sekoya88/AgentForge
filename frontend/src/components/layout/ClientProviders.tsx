"use client";

import { useEffect, useState } from "react";
import { ChatProvider } from "@/contexts/ChatContext";
import { ChatSlideOver } from "@/components/chat/ChatSlideOver";
import { FloatingChatButton } from "@/components/chat/FloatingChatButton";
import { CommandPalette } from "@/components/ui/CommandPalette";

export function ClientProviders({ children }: { children: React.ReactNode }) {
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <ChatProvider>
      {children}
      <FloatingChatButton />
      <ChatSlideOver />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </ChatProvider>
  );
}
