export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  failed?: boolean;
  timestamp: number;
  audioB64?: string | null;
};
