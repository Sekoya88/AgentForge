import Link from "next/link";

export default function Home() {
  return (
    <div className="relative w-full overflow-x-hidden">
      <section className="relative flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center px-6 pb-16 pt-8">
        <div className="mb-12 w-full max-w-2xl">
          <div className="group flex items-center gap-4 rounded-full border border-af-border bg-af-surface-low px-6 py-3 transition-all focus-within:ring-1 focus-within:ring-af-primary/40">
            <span className="material-symbols-outlined text-af-muted-dim">search</span>
            <input
              type="search"
              placeholder="Ask AgentForge anything..."
              className="flex-1 border-none bg-transparent text-sm text-af-on-surface placeholder:text-af-muted-dim focus:ring-0"
              readOnly
              aria-label="Search (coming soon)"
            />
            <div className="flex gap-2">
              <span className="rounded-full border border-af-border bg-af-surface-container px-3 py-1 text-[10px] text-af-muted">
                Deep Agent
              </span>
              <span className="rounded-full border border-af-border bg-af-surface-container px-3 py-1 text-[10px] text-af-muted">
                Red-Team
              </span>
            </div>
          </div>
        </div>
        <div className="relative z-10 mb-10 max-w-4xl text-center">
          <h1 className="mb-4 text-4xl font-extrabold leading-[1.1] tracking-tighter text-white sm:text-5xl md:text-[52px]">
            Build, red-team &amp; <br />
            ship <span className="af-serif-italic text-af-primary">secure</span> agents
          </h1>
          <p className="mx-auto max-w-2xl font-mono text-base leading-relaxed text-af-muted">
            Design multi-agent pipelines visually. Stress-test with adversarial scenarios. Fine-tune on
            serverless GPU. All in one platform.
          </p>
        </div>
        <div className="mb-16 flex flex-col gap-4 sm:flex-row">
          <Link href="/agents" className="af-btn-primary inline-flex justify-center px-8 text-center">
            Open agents
          </Link>
          <Link href="/register" className="af-btn-secondary inline-flex justify-center px-8 text-center">
            Discover more
          </Link>
        </div>
        <div className="absolute bottom-8 left-6 flex items-center gap-3 font-mono text-[11px] uppercase tracking-widest text-af-muted-dim">
          <div className="h-12 w-px bg-gradient-to-b from-af-border to-transparent" />
          <span>Scroll to explore</span>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl grid-cols-1 gap-16 px-8 py-20 md:grid-cols-10 md:gap-20">
        <div className="space-y-6 md:col-span-4">
          <span className="af-kicker">[ ADVANTAGES ]</span>
          <h2 className="text-3xl font-bold leading-tight text-white">
            Outsmart the <span className="af-serif-italic text-af-primary">competition</span> with
            AgentForge
          </h2>
          <Link
            href="/agents"
            className="flex items-center gap-2 text-sm font-bold text-af-primary transition-all hover:gap-4"
          >
            Try out <span className="material-symbols-outlined text-lg">chevron_right</span>
          </Link>
        </div>
        <div className="flex flex-col md:col-span-6">
          {[
            {
              title: "Production-grade orchestration",
              body: "Build complex agent behaviors with LangGraph-powered state machines. Orchestrate long-running workflows with persistent memory and dynamic routing.",
              open: true,
            },
            { title: "Automated security testing", body: "", open: false },
            { title: "Serverless fine-tuning", body: "", open: false },
            { title: "Human-in-the-loop control", body: "", open: false },
          ].map((row, i) => (
            <div
              key={row.title}
              className={`border-t border-af-border py-6 ${i === 3 ? "border-b border-af-border" : ""}`}
            >
              <div className="flex items-start justify-between gap-4">
                <h3 className={`text-base font-bold ${row.open ? "text-white" : "text-white/60"}`}>
                  {row.title}
                </h3>
                <span className="material-symbols-outlined text-af-muted-dim">
                  {row.open ? "remove" : "add"}
                </span>
              </div>
              {row.open && row.body && (
                <p className="mt-4 font-mono text-sm leading-relaxed text-af-muted">{row.body}</p>
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-8 py-20">
        <div className="mb-12">
          <span className="af-kicker mb-4 block">[ CORE FEATURES ]</span>
          <h2 className="max-w-xl text-3xl font-bold text-white">
            What makes AgentForge <span className="af-serif-italic text-af-tertiary">unstoppable</span>
          </h2>
        </div>
        <div className="grid grid-cols-1 gap-12 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["Multi-agent orchestration", "Coordination patterns for heterogeneous agent workflows."],
            ["Adversarial red-teaming", "Jailbreak and prompt-injection style assessments."],
            ["QLoRA fine-tuning", "Efficient domain adaptation on your stack (Modal-ready)."],
            ["Isolated sandboxes", "Python execution for dev — swap for hardened runtime in prod."],
          ].map(([t, d]) => (
            <div key={t} className="space-y-4">
              <h3 className="text-[15px] font-bold tracking-tight text-white">{t}</h3>
              <p className="text-[13px] leading-relaxed text-af-muted">{d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-8 py-20">
        <div className="mb-12">
          <span className="af-kicker mb-4 block">[ AGENTFORGE IN ACTION ]</span>
          <h2 className="text-3xl font-bold text-white">
            Proven <span className="af-serif-italic text-af-primary">performance</span> across benchmarks
          </h2>
        </div>
        <div className="space-y-10">
          {[
            ["Security Score", "Higher is better", ["94%", "71%", "52%"], [94, 71, 52]],
            ["Latency p95", "Lower is better", ["1.2s", "2.8s", "4.1s"], [30, 60, 85]],
            ["Agent reliability", "Execution success", ["99.2%", "87%", "73%"], [99, 87, 73]],
            ["Cost per 1K", "Platform efficiency", ["$2.40", "$4.10", "$8.90"], [25, 45, 90]],
          ].map(([label, sub, vals, widths]) => (
            <div key={String(label)} className="grid grid-cols-1 items-center gap-4 md:grid-cols-4">
              <div className="md:col-span-1">
                <div className="text-sm font-bold text-white">{label}</div>
                <div className="text-xs text-af-muted-dim">{sub}</div>
              </div>
              <div className="space-y-2 md:col-span-3">
                {(vals as string[]).map((v, j) => (
                  <div key={v} className="flex items-center gap-3">
                    <div
                      className={`h-2 rounded-full ${j === 0 ? "bg-af-primary" : "bg-af-border"}`}
                      style={{ width: `${(widths as number[])[j]}%` }}
                    />
                    <span className={`text-xs ${j === 0 ? "text-white" : "text-af-muted-dim"}`}>
                      {v}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-8 py-20">
        <div className="mb-12">
          <span className="af-kicker mb-4 block">[ PRODUCTS ]</span>
          <h2 className="text-3xl font-bold text-white">
            Tools for every <span className="af-serif-italic text-af-secondary">innovator</span>
          </h2>
        </div>
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["API", "Forge Engine", "High-performance runtime for agents with unified memory."],
            ["STUDIO", "Designer Studio", "Visual workflow builder for multi-agent graphs."],
            ["SHIELD", "Forge Shield", "Red-teaming suite and campaign reports."],
            ["CLI", "Forge CLI", "Manage jobs and exports from your terminal."],
          ].map(([tag, title, desc], idx) => (
            <div key={title} className="group flex flex-col">
              <div
                className={`mb-6 h-40 w-full rounded-xl bg-gradient-to-br opacity-80 transition-transform group-hover:scale-[1.02] ${
                  idx === 0
                    ? "from-[#4F46E5] via-[#7C3AED] to-[#2DD4BF]"
                    : idx === 1
                      ? "from-[#7C3AED] via-[#2DD4BF] to-[#4F46E5]"
                      : idx === 2
                        ? "from-[#2DD4BF] via-[#4F46E5] to-[#7C3AED]"
                        : "from-[#4F46E5] to-[#13121c]"
                } relative overflow-hidden`}
              >
                <div className="absolute inset-0 bg-af-bg/20" />
              </div>
              <span className="mb-3 inline-block w-fit rounded bg-af-border px-2 py-0.5 text-[10px] text-af-muted">
                {tag}
              </span>
              <h3 className="mb-2 text-[15px] font-bold text-white">{title}</h3>
              <p className="mb-4 flex-grow text-[13px] text-af-muted">{desc}</p>
              <Link href="/agents" className="text-xs font-bold text-af-primary transition-transform hover:translate-x-1">
                Get started &gt;
              </Link>
            </div>
          ))}
        </div>
      </section>

      <section className="relative mx-auto max-w-7xl px-8 py-24 text-center">
        <div className="relative z-10">
          <span className="af-kicker mb-6 block">[ Start Now ]</span>
          <h2 className="mb-4 text-4xl font-bold text-white md:text-[44px]">
            Join the <span className="af-serif-italic text-af-primary">revolution</span>
          </h2>
          <p className="mx-auto mb-12 max-w-xl font-mono text-sm text-af-muted">
            The next generation of intelligence is autonomous, secure, and ready for deployment. Start
            building today.
          </p>
          <Link
            href="/register"
            className="inline-block rounded-xl bg-white px-12 py-4 text-lg font-bold text-af-bg transition-all hover:shadow-[0_0_30px_rgba(255,255,255,0.25)] active:scale-95"
          >
            START NOW
          </Link>
        </div>
      </section>

      <footer className="w-full border-t border-af-border bg-af-bg pb-10 pt-16">
        <div className="mx-auto mb-12 grid max-w-7xl grid-cols-2 gap-12 px-8 md:grid-cols-4">
          <div className="col-span-2 md:col-span-1">
            <div className="mb-6 font-mono text-lg font-bold text-white">AgentForge</div>
            <p className="font-mono text-xs leading-relaxed text-af-muted-dim">
              Engineering the future of autonomous intelligence.
            </p>
          </div>
          <div>
            <h4 className="mb-6 font-mono text-[13px] font-bold text-white">Platform</h4>
            <div className="flex flex-col gap-3 font-mono text-xs text-af-muted-dim">
              <span>LangGraph</span>
              <span>Promptfoo</span>
              <span>Modal</span>
            </div>
          </div>
          <div>
            <h4 className="mb-6 font-mono text-[13px] font-bold text-white">Solutions</h4>
            <div className="flex flex-col gap-3">
              <Link href="/agents" className="font-mono text-xs text-af-muted-dim hover:text-teal-400">
                Agent builder
              </Link>
              <Link href="/campaigns" className="font-mono text-xs text-af-muted-dim hover:text-teal-400">
                Red-team
              </Link>
              <Link href="/finetune" className="font-mono text-xs text-af-muted-dim hover:text-teal-400">
                Fine-tune
              </Link>
              <Link href="/skills" className="font-mono text-xs text-af-muted-dim hover:text-teal-400">
                Skills
              </Link>
            </div>
          </div>
          <div>
            <h4 className="mb-6 font-mono text-[13px] font-bold text-white">Project</h4>
            <div className="flex flex-col gap-3">
              <Link href="/login" className="font-mono text-xs text-af-muted-dim hover:text-teal-400">
                Login
              </Link>
              <Link href="/register" className="font-mono text-xs text-af-muted-dim hover:text-teal-400">
                Register
              </Link>
            </div>
          </div>
        </div>
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 border-t border-white/5 px-8 pt-8 md:flex-row">
          <div className="font-mono text-xs text-af-muted-dim">© {new Date().getFullYear()} AgentForge.</div>
          <div className="flex gap-6 font-mono text-xs text-af-muted-dim">
            <span>Privacy</span>
            <span>Terms</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
