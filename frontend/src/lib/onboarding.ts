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

/** Dashboard counts → step IDs we can infer without extra API calls. */
export type OnboardingSyncInput = {
  agents: number;
  knowledge_sources: number;
  campaigns: number;
};

export function stepIdsCompletedFromStats(s: OnboardingSyncInput): string[] {
  const done: string[] = [];
  if (s.agents > 0) done.push("create_agent");
  if (s.knowledge_sources > 0) done.push("ingest_knowledge");
  if (s.campaigns > 0) done.push("run_campaign");
  return done;
}

export const PRODUCT_TOUR_V1_DONE_KEY = "af_product_tour_v1_done";

export function isProductTourV1Done(): boolean {
  if (typeof window === "undefined") return true;
  return localStorage.getItem(PRODUCT_TOUR_V1_DONE_KEY) === "true";
}

export function setProductTourV1Done(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(PRODUCT_TOUR_V1_DONE_KEY, "true");
}
