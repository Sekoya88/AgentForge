export type AgentStep = {
  event: "tool_call" | "tool_result" | "skill" | "agent_start" | "agent_end" | "complete" | "error";
  label: string;       // human-readable: "web_search", "summarize", "llm_node"
  durationMs?: number;
  timestamp: number;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  failed?: boolean;
  timestamp: number;
  audioB64?: string | null;
  steps?: AgentStep[];  // populated when execution completes
};
