export type AgentStep = {
  event:
    | "tool_call" | "tool_result" | "skill" | "skill_summary"
    | "agent_start" | "agent_end"
    | "llm_start" | "llm_end"
    | "rag_search"
    | "complete" | "error";
  label: string;
  phase?: string;
  durationMs?: number;
  timestamp: number;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  failed?: boolean;
  timestamp: number;
  lastTokenAt?: number;
  audioB64?: string | null;
  steps?: AgentStep[];  // populated when execution completes
};
