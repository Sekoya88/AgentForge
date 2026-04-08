const STORAGE_KEY = "af_onboarding_dismissed";

export type OnboardingStep = {
  id: string;
  label: string;
  description: string;
  icon: string;
  href: string;
  cta: string;
};

export const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    id: "create_agent",
    label: "Create your first agent",
    description: "Design an LLM agent with a system prompt and run it.",
    icon: "smart_toy",
    href: "/agents/new",
    cta: "Create agent",
  },
  {
    id: "open_forge",
    label: "Chat in Forge",
    description: "Use Forge to chat with any model — web search and Python REPL included.",
    icon: "bolt",
    href: "/forge",
    cta: "Open Forge",
  },
  {
    id: "ingest_knowledge",
    label: "Ingest knowledge",
    description: "Upload a document or paste text to build your RAG corpus.",
    icon: "menu_book",
    href: "/knowledge",
    cta: "Add knowledge",
  },
  {
    id: "run_campaign",
    label: "Run a red-team campaign",
    description: "Stress-test your agent with 12 adversarial attack categories.",
    icon: "security",
    href: "/agents",
    cta: "Go to agents",
  },
  {
    id: "finetune_model",
    label: "Fine-tune a model",
    description: "Launch a LoRA/QLoRA training job on GPU via Modal.",
    icon: "model_training",
    href: "/finetune/new",
    cta: "New fine-tune job",
  },
];

export function isOnboardingDismissed(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(STORAGE_KEY) === "true";
}

export function dismissOnboarding(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, "true");
}

export function getCompletedSteps(): string[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem("af_onboarding_completed") ?? "[]") as string[];
  } catch {
    return [];
  }
}

export function markStepComplete(id: string): void {
  if (typeof window === "undefined") return;
  const current = getCompletedSteps();
  if (!current.includes(id)) {
    localStorage.setItem("af_onboarding_completed", JSON.stringify([...current, id]));
  }
}
