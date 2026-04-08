import React from "react";

type Message = {
  role: "user" | "assistant" | "system" | "tool";
  content: string;
};

interface ChatUIProps {
  messages: Message[];
}

const ROLE_LABEL: Record<string, string> = {
  assistant: "Agent",
  system: "System",
  tool: "Tool",
};

export function ChatUI({ messages }: ChatUIProps) {
  if (!messages || messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <span className="material-symbols-outlined mb-3 text-4xl text-af-muted-dim">chat_bubble_outline</span>
        <p className="text-sm text-af-muted">No messages yet.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {messages.map((msg, idx) => {
        const isUser = msg.role === "user";
        const isTool = msg.role === "tool";
        const isSystem = msg.role === "system";

        if (isSystem) {
          return (
            <div key={idx} className="flex justify-center">
              <span className="rounded-full border border-af-border/40 bg-af-surface-void px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-af-muted-dim">
                System context set
              </span>
            </div>
          );
        }

        if (isTool) {
          return (
            <div key={idx} className="mx-auto w-full max-w-[90%]">
              <div className="rounded-lg border border-af-border/40 bg-af-surface-void/60 px-3 py-2">
                <div className="mb-1 flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-sm text-af-muted-dim">build</span>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-af-muted-dim">Tool result</span>
                </div>
                <pre className="af-mono overflow-x-auto whitespace-pre-wrap text-xs text-af-muted">
                  {msg.content}
                </pre>
              </div>
            </div>
          );
        }

        return (
          <div
            key={idx}
            className={`flex items-end gap-2 ${isUser ? "flex-row-reverse" : "flex-row"}`}
          >
            {!isUser && (
              <div className="mb-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-af-primary/30 bg-af-primary/10">
                <span className="material-symbols-outlined text-sm text-af-primary">smart_toy</span>
              </div>
            )}
            <div className={`flex max-w-[78%] flex-col gap-1 ${isUser ? "items-end" : "items-start"}`}>
              {!isUser && (
                <span className="ml-1 text-[10px] font-bold uppercase tracking-wider text-af-muted-dim">
                  {ROLE_LABEL[msg.role] ?? msg.role}
                </span>
              )}
              <div
                className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                  isUser
                    ? "rounded-br-sm bg-af-primary text-white"
                    : "rounded-bl-sm border border-af-border/60 bg-af-surface-high text-af-on-surface"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
