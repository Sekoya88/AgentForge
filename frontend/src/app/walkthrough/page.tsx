import Link from "next/link";
import { ToolShell } from "@/components/layout/ToolShell";

const FLOWS: {
  title: string;
  goal: string;
  steps: string[];
  links: { href: string; label: string }[];
}[] = [
  {
    title: "RAG support agent",
    goal: "Answer from your docs only, with retrieve + LLM.",
    steps: [
      "Index files or URL at /knowledge (PDF, text, markdown supported).",
      "Create an agent and open the builder.",
      "Add a Tool node (retrieve) then an LLM; connect and run.",
      "Check /executions for the trace.",
    ],
    links: [
      { href: "/knowledge", label: "Knowledge" },
      { href: "/agents/new", label: "New agent" },
    ],
  },
  {
    title: "Scheduled digest + webhook",
    goal: "Cron run + notify your endpoint when execution completes.",
    steps: [
      "Build an agent (e.g. web_search → LLM).",
      "Add a schedule on the agent detail page.",
      "Register a webhook in /settings for execution.completed.",
      "Use Run now or wait for cron; verify payload at your URL.",
    ],
    links: [
      { href: "/agents", label: "Agents" },
      { href: "/settings", label: "Settings" },
    ],
  },
  {
    title: "Voice assistant",
    goal: "ASR → LLM → TTS pipeline.",
    steps: [
      "Use the Voice Assistant template from /agents/new.",
      "Add API keys in /settings.",
      "Execute via POST …/execute/audio (see API docs).",
    ],
    links: [
      { href: "/agents/new", label: "New agent" },
      { href: "/settings", label: "Settings" },
    ],
  },
  {
    title: "Red-team campaign",
    goal: "Score agent robustness before shipping.",
    steps: [
      "Open /campaigns and start a campaign for an agent.",
      "Review scores and failing prompts.",
      "Iterate prompts or graph in the builder.",
    ],
    links: [
      { href: "/campaigns", label: "Campaigns" },
      { href: "/agents", label: "Agents" },
    ],
  },
  {
    title: "Fine-tune & deploy",
    goal: "Train on Modal and point an agent at your model.",
    steps: [
      "Create a job under /finetune.",
      "Monitor training; deploy when ready.",
      "Set agent model_config to finetuned provider.",
    ],
    links: [
      { href: "/finetune", label: "Finetune" },
      { href: "/agents", label: "Agents" },
    ],
  },
];

export default function WalkthroughPage() {
  return (
    <ToolShell active="walkthrough">
      <div className="mx-auto max-w-4xl">
        <p className="af-kicker mb-2 text-af-primary">[ WALKTHROUGH ]</p>
        <h1 className="mb-2 font-sans text-3xl font-bold tracking-tight text-white md:text-4xl">
          Try these flows
        </h1>
        <p className="mb-8 max-w-2xl text-sm text-af-muted">
          Hands-on paths aligned with the product roadmap. Complete the{" "}
          <Link href="/dashboard" className="text-af-primary hover:underline">
            dashboard checklist
          </Link>{" "}
          first, then pick a scenario below.
        </p>

        <ul className="space-y-6">
          {FLOWS.map((flow) => (
            <li
              key={flow.title}
              className="rounded-xl border border-af-border/50 bg-af-surface-container/40 p-6 backdrop-blur-sm"
            >
              <h2 className="text-lg font-bold text-af-on-surface">{flow.title}</h2>
              <p className="mt-1 text-sm text-af-muted">{flow.goal}</p>
              <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm text-af-on-surface/90">
                {flow.steps.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ol>
              <div className="mt-4 flex flex-wrap gap-2">
                {flow.links.map((l) => (
                  <Link
                    key={l.href + l.label}
                    href={l.href}
                    className="inline-flex items-center gap-1 rounded-lg border border-af-primary/40 bg-af-primary/10 px-3 py-1.5 text-xs font-bold text-af-primary hover:bg-af-primary/20"
                  >
                    {l.label}
                    <span className="material-symbols-outlined text-sm">arrow_forward</span>
                  </Link>
                ))}
              </div>
            </li>
          ))}
        </ul>

        <p className="mt-10 text-xs text-af-muted-dim">
          Use the dashboard onboarding checklist and Help → Walkthrough for guided steps inside the app.
        </p>
      </div>
    </ToolShell>
  );
}
