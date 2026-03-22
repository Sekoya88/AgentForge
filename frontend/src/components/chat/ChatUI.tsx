import React from "react";

type Message = {
  role: "user" | "assistant" | "system" | "tool";
  content: string;
};

interface ChatUIProps {
  messages: Message[];
}

export function ChatUI({ messages }: ChatUIProps) {
  if (!messages || messages.length === 0) {
    return <div className="text-sm text-af-muted-dim">No messages yet.</div>;
  }

  return (
    <div className="flex flex-col gap-4">
      {messages.map((msg, idx) => {
        const isUser = msg.role === "user";
        const isSystem = msg.role === "system";
        const isTool = msg.role === "tool";

        return (
          <div
            key={idx}
            className={`flex ${isUser ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-5 py-3 text-sm leading-relaxed ${
                isUser
                  ? "bg-af-primary text-black"
                  : isSystem || isTool
                    ? "bg-af-surface-void text-af-muted border border-af-border"
                    : "bg-af-surface-high border border-af-border text-af-on-surface"
              }`}
            >
              {msg.role !== "user" && (
                <div className="mb-1 text-[10px] font-bold uppercase tracking-wider text-af-muted-dim">
                  {msg.role}
                </div>
              )}
              <div className="whitespace-pre-wrap">{msg.content}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
