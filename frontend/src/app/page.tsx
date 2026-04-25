"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ScrollReveal } from "@/components/fx/ScrollReveal";
import { EntropyBackground } from "@/components/fx/EntropyBackground";
import { useScrollReveal } from "@/hooks/useScrollReveal";
import { useCountUp } from "@/hooks/useCountUp";

// ── Benchmark row with animated bar + count-up ────────────────────────────────
function BenchmarkRow({
  label,
  sub,
  vals,
  widths,
}: {
  label: string;
  sub: string;
  vals: string[];
  widths: number[];
}) {
  const [ref, visible] = useScrollReveal<HTMLDivElement>({ threshold: 0.2 });
  const pct = useCountUp(widths[0], visible);

  return (
    <div ref={ref} className="grid grid-cols-1 items-center gap-4 md:grid-cols-4">
      <div className="md:col-span-1">
        <div className="text-sm font-bold text-white">{label}</div>
        <div className="text-xs text-af-muted-dim">{sub}</div>
      </div>
      <div className="space-y-2 md:col-span-3">
        {vals.map((v, j) => (
          <div key={v} className="flex items-center gap-3">
            <div className="relative h-2 overflow-hidden rounded-full bg-af-border/50" style={{ width: `${widths[j]}%` }}>
              <div
                className={`absolute inset-y-0 left-0 rounded-full transition-all duration-1000 ease-out ${
                  j === 0
                    ? "bg-gradient-to-r from-af-indigo to-af-primary"
                    : "bg-af-border"
                }`}
                style={{ width: visible ? "100%" : "0%" }}
              />
              {j === 0 && visible && (
                <div className="absolute inset-y-0 right-0 w-8 bg-gradient-to-r from-transparent to-af-primary/40 blur-sm" />
              )}
            </div>
            <span className={`text-xs font-mono ${j === 0 ? "text-af-primary font-bold" : "text-af-muted-dim"}`}>
              {j === 0 ? (vals[0].includes("%") ? `${pct}%` : vals[0].includes("s") ? `${(pct / 10).toFixed(1)}s` : `$${(pct / 10).toFixed(2)}`) : v}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function Home() {
  const [ready, setReady] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [searchFocused, setSearchFocused] = useState(false);
  const [openAccordion, setOpenAccordion] = useState(0);

  useEffect(() => {
    setLoggedIn(Boolean(localStorage.getItem("access_token")));
    setReady(true);
  }, []);

  if (!ready) return null;

  return (
    <div className="relative w-full overflow-x-hidden">
      {/* Full landing-page entropy — covers entire scroll height */}
      <EntropyBackground mode="page" />
      {/* ── HERO ── */}
      <section className="relative flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center px-6 pb-16 pt-8">

        {/* Glassmorphic search bar */}
        <div className="mb-12 w-full max-w-2xl af-motion-fade-in" style={{ animationDelay: "100ms" }}>
          <div
            className={`group flex items-center gap-4 rounded-full px-6 py-3 transition-all duration-300 ${
              searchFocused
                ? "af-glass-elevated shadow-[0_0_40px_rgba(195,192,255,0.12)]"
                : "af-glass-interactive"
            }`}
          >
            <span className="material-symbols-outlined text-af-muted-dim transition-colors group-focus-within:text-af-primary">
              search
            </span>
            <input
              type="search"
              placeholder="Ask AgentForge anything..."
              className="flex-1 border-none bg-transparent text-sm text-af-on-surface placeholder:text-af-muted-dim focus:ring-0 focus:outline-none"
              readOnly
              aria-label="Search (coming soon)"
              onFocus={() => setSearchFocused(true)}
              onBlur={() => setSearchFocused(false)}
            />
            <div className="flex gap-2">
              <span className="rounded-full border border-af-border bg-af-surface-container/60 px-3 py-1 text-[10px] text-af-muted">
                Deep Agent
              </span>
              <span className="rounded-full border border-af-border bg-af-surface-container/60 px-3 py-1 text-[10px] text-af-muted">
                Red-Team
              </span>
            </div>
          </div>
        </div>

        {/* Hero text */}
        <div className="relative z-10 mb-10 max-w-4xl text-center">
          <h1
            className="mb-4 text-4xl font-extrabold leading-[1.1] tracking-tighter text-white sm:text-5xl md:text-[56px] af-motion-fade-in"
            style={{ animationDelay: "200ms" }}
          >
            Build, red-team &amp; <br />
            ship{" "}
            <span className="af-serif-italic bg-gradient-to-r from-af-primary to-af-secondary bg-clip-text text-transparent">
              secure
            </span>{" "}
            agents
          </h1>
          <p
            className="mx-auto max-w-2xl font-mono text-base leading-relaxed text-af-muted af-motion-fade-in"
            style={{ animationDelay: "350ms" }}
          >
            Design multi-agent pipelines visually. Stress-test with adversarial scenarios. Fine-tune on
            serverless GPU. All in one platform.
          </p>
        </div>

        {/* CTA buttons */}
        <div
          className="mb-16 flex flex-col gap-4 sm:flex-row af-motion-fade-in"
          style={{ animationDelay: "500ms" }}
        >
          {loggedIn ? (
            <Link
              href="/dashboard"
              className="group relative inline-flex items-center justify-center overflow-hidden rounded-xl bg-af-inverse px-8 py-3 font-bold text-af-surface-dim transition-all hover:shadow-[0_0_30px_rgba(195,192,255,0.25)] active:scale-[0.97]"
            >
              <span className="absolute inset-0 bg-gradient-to-r from-af-indigo/20 to-af-primary/20 opacity-0 transition-opacity group-hover:opacity-100" />
              <span className="relative">Go to Dashboard</span>
            </Link>
          ) : (
            <Link
              href="/register"
              className="group relative inline-flex items-center justify-center overflow-hidden rounded-xl bg-af-inverse px-8 py-3 font-bold text-af-surface-dim transition-all hover:shadow-[0_0_30px_rgba(195,192,255,0.25)] active:scale-[0.97]"
            >
              <span className="absolute inset-0 bg-gradient-to-r from-af-indigo/20 to-af-primary/20 opacity-0 transition-opacity group-hover:opacity-100" />
              <span className="relative">Get started</span>
            </Link>
          )}
          <Link
            href="/agents"
            className="inline-flex items-center justify-center rounded-xl border border-af-border/60 bg-transparent px-8 py-3 font-bold text-white/80 backdrop-blur-sm transition-all hover:border-af-primary/40 hover:bg-af-primary/5 hover:text-white active:scale-[0.97]"
          >
            Open agents
          </Link>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-8 left-6 flex items-center gap-3 font-mono text-[11px] uppercase tracking-widest text-af-muted-dim">
          <div className="h-12 w-px bg-gradient-to-b from-af-border to-transparent" />
          <span className="af-glow-pulse">Scroll to explore</span>
        </div>
      </section>

      {/* ── ADVANTAGES ── */}
      <section className="mx-auto grid max-w-7xl grid-cols-1 gap-16 px-8 py-20 md:grid-cols-10 md:gap-20">
        <ScrollReveal className="space-y-6 md:col-span-4">
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
        </ScrollReveal>

        <div className="flex flex-col md:col-span-6">
          {[
            {
              title: "Production-grade orchestration",
              body: "Build complex agent behaviors with LangGraph-powered state machines. Orchestrate long-running workflows with persistent memory and dynamic routing.",
            },
            { title: "Automated security testing", body: "Run 12-vector adversarial campaigns against your agents in CI. Track security scores, baselines, and regressions over time." },
            { title: "Serverless fine-tuning", body: "QLoRA fine-tune on Modal GPU from your agent's own production traces. One click from execution history to deployed model." },
            { title: "Human-in-the-loop control", body: "Pause any agent mid-execution for approval. Configurable interrupt policies, timeout escalation, and audit trail." },
          ].map((row, i) => {
            const isOpen = openAccordion === i;
            return (
              <ScrollReveal key={row.title} delay={i * 60}>
                <div
                  className={`border-t border-af-border/60 py-6 transition-colors hover:border-af-primary/30 ${i === 3 ? "border-b border-af-border/60" : ""}`}
                >
                  <button
                    type="button"
                    className="flex w-full items-start justify-between gap-4 text-left"
                    onClick={() => setOpenAccordion(isOpen ? -1 : i)}
                    aria-expanded={isOpen}
                  >
                    <h3 className={`text-base font-bold transition-colors ${isOpen ? "text-white" : "text-white/60 hover:text-white/80"}`}>
                      {row.title}
                    </h3>
                    <span
                      className="material-symbols-outlined shrink-0 text-af-muted-dim transition-transform duration-300"
                      style={{ transform: isOpen ? "rotate(45deg)" : "rotate(0deg)" }}
                    >
                      add
                    </span>
                  </button>
                  <div
                    className="overflow-hidden transition-all duration-300 ease-in-out"
                    style={{ maxHeight: isOpen ? "200px" : "0px", opacity: isOpen ? 1 : 0 }}
                  >
                    <p className="mt-4 font-mono text-sm leading-relaxed text-af-muted">{row.body}</p>
                  </div>
                </div>
              </ScrollReveal>
            );
          })}
        </div>
      </section>

      {/* ── CORE FEATURES ── */}
      <section className="mx-auto max-w-7xl px-8 py-20">
        <ScrollReveal className="mb-12">
          <span className="af-kicker mb-4 block">[ CORE FEATURES ]</span>
          <h2 className="max-w-xl text-3xl font-bold text-white">
            What makes AgentForge{" "}
            <span className="af-serif-italic text-af-tertiary">unstoppable</span>
          </h2>
        </ScrollReveal>
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["Multi-agent orchestration", "Coordination patterns for heterogeneous agent workflows.", "hub"],
            ["Adversarial red-teaming", "Jailbreak and prompt-injection style assessments.", "security"],
            ["QLoRA fine-tuning", "Efficient domain adaptation on your stack (Modal-ready).", "model_training"],
            ["Isolated sandboxes", "Python execution for dev — swap for hardened runtime in prod.", "biotech"],
          ].map(([t, d, icon], i) => (
            <ScrollReveal key={String(t)} delay={i * 80}>
              <div className="af-glass-interactive group rounded-xl p-6 space-y-4">
                <span className="material-symbols-outlined text-af-primary/70 group-hover:text-af-primary transition-colors">{icon}</span>
                <h3 className="text-[15px] font-bold tracking-tight text-white">{t}</h3>
                <p className="text-[13px] leading-relaxed text-af-muted">{d}</p>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </section>

      {/* ── BENCHMARKS ── */}
      <section className="mx-auto max-w-7xl px-8 py-20">
        <ScrollReveal className="mb-12">
          <span className="af-kicker mb-4 block">[ AGENTFORGE IN ACTION ]</span>
          <h2 className="text-3xl font-bold text-white">
            Proven <span className="af-serif-italic text-af-primary">performance</span> across benchmarks
          </h2>
        </ScrollReveal>
        <div className="space-y-10">
          <BenchmarkRow label="Security Score" sub="Higher is better" vals={["94%", "71%", "52%"]} widths={[94, 71, 52]} />
          <BenchmarkRow label="Latency p95" sub="Lower is better" vals={["1.2s", "2.8s", "4.1s"]} widths={[30, 60, 85]} />
          <BenchmarkRow label="Agent reliability" sub="Execution success" vals={["99.2%", "87%", "73%"]} widths={[99, 87, 73]} />
          <BenchmarkRow label="Cost per 1K" sub="Platform efficiency" vals={["$2.40", "$4.10", "$8.90"]} widths={[25, 45, 90]} />
        </div>
      </section>

      {/* ── PRODUCTS ── */}
      <section className="mx-auto max-w-7xl px-8 py-20">
        <ScrollReveal className="mb-12">
          <span className="af-kicker mb-4 block">[ PRODUCTS ]</span>
          <h2 className="text-3xl font-bold text-white">
            Tools for every <span className="af-serif-italic text-af-secondary">innovator</span>
          </h2>
        </ScrollReveal>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { tag: "API", title: "Forge Engine", desc: "High-performance runtime for agents with unified memory.", gradient: "from-[#4F46E5] via-[#7C3AED] to-[#2DD4BF]" },
            { tag: "STUDIO", title: "Designer Studio", desc: "Visual workflow builder for multi-agent graphs.", gradient: "from-[#7C3AED] via-[#2DD4BF] to-[#4F46E5]" },
            { tag: "SHIELD", title: "Forge Shield", desc: "Red-teaming suite and campaign reports.", gradient: "from-[#2DD4BF] via-[#4F46E5] to-[#7C3AED]" },
            { tag: "CLI", title: "Forge CLI", desc: "Manage jobs and exports from your terminal.", gradient: "from-[#4F46E5] to-[#7C3AED]" },
          ].map(({ tag, title, desc, gradient }, i) => (
            <ScrollReveal key={title} delay={i * 70}>
              <div className="group flex flex-col af-glass-interactive rounded-xl overflow-hidden cursor-pointer">
                <div
                  className={`h-36 w-full bg-gradient-to-br opacity-80 group-hover:opacity-100 transition-all duration-500 group-hover:scale-[1.03] ${gradient} relative overflow-hidden`}
                >
                  <div className="absolute inset-0 bg-af-bg/10 group-hover:bg-transparent transition-colors" />
                  {/* Subtle grid overlay */}
                  <div className="absolute inset-0 opacity-20" style={{
                    backgroundImage: "repeating-linear-gradient(0deg,transparent,transparent 20px,rgba(255,255,255,0.05) 20px,rgba(255,255,255,0.05) 21px),repeating-linear-gradient(90deg,transparent,transparent 20px,rgba(255,255,255,0.05) 20px,rgba(255,255,255,0.05) 21px)"
                  }} />
                </div>
                <div className="p-5 flex flex-col flex-grow">
                  <span className="mb-3 inline-block w-fit rounded bg-af-border/60 px-2 py-0.5 text-[10px] font-mono text-af-muted">
                    {tag}
                  </span>
                  <h3 className="mb-2 text-[15px] font-bold text-white">{title}</h3>
                  <p className="mb-4 flex-grow text-[13px] text-af-muted leading-relaxed">{desc}</p>
                  <Link href="/agents" className="text-xs font-bold text-af-primary transition-all hover:translate-x-1 inline-flex items-center gap-1">
                    Get started
                    <span className="material-symbols-outlined text-sm">chevron_right</span>
                  </Link>
                </div>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="relative mx-auto max-w-7xl px-8 py-24 text-center">
        <ScrollReveal className="relative z-10">
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
            className="group relative inline-block overflow-hidden rounded-xl bg-white px-12 py-4 text-lg font-bold text-af-bg transition-all hover:shadow-[0_0_40px_rgba(195,192,255,0.3)] active:scale-95 af-glow-pulse"
          >
            <span className="absolute inset-0 translate-x-[-100%] bg-gradient-to-r from-transparent via-white/20 to-transparent transition-transform duration-700 group-hover:translate-x-[100%]" />
            START NOW
          </Link>
        </ScrollReveal>
        {/* Background glow behind CTA */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="h-64 w-64 rounded-full bg-af-primary/5 blur-[80px]" />
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="w-full border-t border-af-border/60 pb-10 pt-16 af-glass-void">
        <div className="mx-auto mb-12 grid max-w-7xl grid-cols-2 gap-12 px-8 md:grid-cols-4">
          <div className="col-span-2 md:col-span-1">
            <div className="mb-6 font-mono text-lg font-bold text-white">AgentForge</div>
            <p className="font-mono text-xs leading-relaxed text-af-muted-dim">
              Engineering the future of autonomous intelligence.
            </p>
            <span className="mt-4 inline-block rounded-full border border-af-border/60 px-3 py-1 font-mono text-[10px] text-af-muted-dim">
              v0.1.0-research
            </span>
          </div>
          <div>
            <h4 className="mb-6 font-mono text-[13px] font-bold text-white">Platform</h4>
            <div className="flex flex-col gap-3 font-mono text-xs text-af-muted-dim">
              <span className="transition-colors hover:text-af-muted cursor-default">LangGraph</span>
              <span className="transition-colors hover:text-af-muted cursor-default">Promptfoo</span>
              <span className="transition-colors hover:text-af-muted cursor-default">Modal</span>
            </div>
          </div>
          <div>
            <h4 className="mb-6 font-mono text-[13px] font-bold text-white">Solutions</h4>
            <div className="flex flex-col gap-3">
              {[["Agent builder", "/agents"], ["Red-team", "/campaigns"], ["Fine-tune", "/finetune"], ["Skills", "/skills"]].map(([label, href]) => (
                <Link key={href} href={href} className="font-mono text-xs text-af-muted-dim transition-colors hover:text-af-tertiary">
                  {label}
                </Link>
              ))}
            </div>
          </div>
          <div>
            <h4 className="mb-6 font-mono text-[13px] font-bold text-white">Project</h4>
            <div className="flex flex-col gap-3">
              <Link href="/login" className="font-mono text-xs text-af-muted-dim transition-colors hover:text-af-tertiary">Login</Link>
              <Link href="/register" className="font-mono text-xs text-af-muted-dim transition-colors hover:text-af-tertiary">Register</Link>
            </div>
          </div>
        </div>
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 border-t border-white/5 px-8 pt-8 md:flex-row">
          <div className="font-mono text-xs text-af-muted-dim">© {new Date().getFullYear()} AgentForge.</div>
          <div className="flex gap-6 font-mono text-xs text-af-muted-dim">
            <span className="cursor-default hover:text-af-muted transition-colors">Privacy</span>
            <span className="cursor-default hover:text-af-muted transition-colors">Terms</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
