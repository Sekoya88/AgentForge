export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  failed?: boolean;
  timestamp: number;
};
