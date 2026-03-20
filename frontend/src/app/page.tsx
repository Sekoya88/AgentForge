import Link from "next/link";

export default function Home() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Build & run agents</h1>
      <p className="max-w-xl text-neutral-400">
        Create agents backed by LangGraph, execute them with a mock orchestrator, and iterate toward
        sandbox, red-team, and fine-tuning features from the roadmap.
      </p>
      <div className="flex flex-wrap gap-3">
        <Link
          href="/agents"
          className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-medium text-black hover:bg-cyan-400"
        >
          Open agents
        </Link>
        <Link
          href="/register"
          className="rounded-lg border border-neutral-700 px-4 py-2 text-sm hover:border-neutral-500"
        >
          Create account
        </Link>
      </div>
    </div>
  );
}
