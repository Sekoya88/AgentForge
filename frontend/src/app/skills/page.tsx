"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ToolShell } from "@/components/layout/ToolShell";
import { ApiError, api } from "@/lib/api";

type Skill = {
  id: string;
  name: string;
  is_public: boolean;
  security_validated: boolean;
};

export default function SkillsPage() {
  const router = useRouter();
  const [skills, setSkills] = useState<Skill[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const data = await api<Skill[]>("/api/v1/skills");
        if (!c) setSkills(data);
      } catch (e) {
        if (!c) {
          if (e instanceof ApiError && e.status === 401) router.push("/login");
          else setError(e instanceof Error ? e.message : "Failed");
        }
      }
    })();
    return () => {
      c = true;
    };
  }, [router]);

  return (
    <ToolShell active="skills">
      <div className="mb-16">
        <div className="mb-4 text-xs font-bold tracking-[0.3em] text-indigo-400">[ SKILLS ]</div>
        <h1 className="mb-6 text-5xl font-bold tracking-tighter md:text-7xl">
          Agent{" "}
          <span className="af-serif-italic font-normal tracking-normal text-indigo-300">skills</span>
        </h1>
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <p className="max-w-xl leading-relaxed text-af-muted">
            Extend agents with callable modules. Register Python stubs backed by the API.
          </p>
          <Link
            href="/skills/new"
            className="af-btn-primary inline-flex shrink-0 items-center gap-2 px-8 py-3 text-sm"
          >
            <span className="material-symbols-outlined text-lg">add_circle</span>
            New skill
          </Link>
        </div>
      </div>

      {error && (
        <p className="mb-6 rounded-lg border border-af-error/30 bg-af-error/10 px-4 py-3 text-sm text-af-error">
          {error}
        </p>
      )}

      {skills && skills.length === 0 && (
        <div className="rounded-xl border border-dashed border-af-border/60 p-12 text-center">
          <p className="text-af-muted">No skills yet.</p>
          <Link href="/skills/new" className="mt-4 inline-block text-sm font-bold text-af-primary hover:underline">
            Create one →
          </Link>
        </div>
      )}

      {skills && skills.length > 0 && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
          {skills.map((s) => (
            <div
              key={s.id}
              className="group relative rounded-xl border border-white/5 bg-af-surface-container p-6 transition-all duration-300 hover:border-indigo-500/40"
            >
              <div className="mb-8 flex justify-between">
                <div className="rounded-lg bg-indigo-500/10 p-3 text-indigo-400 transition-colors group-hover:bg-indigo-500 group-hover:text-white">
                  <span className="material-symbols-outlined text-2xl">code_blocks</span>
                </div>
                <span className="rounded bg-white/5 px-2 py-1 text-[10px] font-bold text-af-muted-dim">
                  {s.is_public ? "PUBLIC" : "PRIVATE"}
                </span>
              </div>
              <h3 className="mb-3 text-xl font-bold text-white">{s.name}</h3>
              <p className="mb-6 text-sm leading-relaxed text-af-muted">
                {s.security_validated ? "Security validated." : "Pending validation."}
              </p>
              <p className="font-mono text-[10px] text-af-muted-dim">id {s.id.slice(0, 8)}…</p>
            </div>
          ))}
        </div>
      )}
    </ToolShell>
  );
}
