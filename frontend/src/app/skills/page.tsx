"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Skills</h1>
        <Link
          href="/skills/new"
          className="rounded-md bg-cyan-500 px-3 py-1.5 text-sm font-medium text-black"
        >
          New skill
        </Link>
      </div>
      {error && <p className="text-sm text-amber-400">{error}</p>}
      {skills && skills.length === 0 && <p className="text-neutral-500">No skills yet.</p>}
      {skills && skills.length > 0 && (
        <ul className="divide-y divide-neutral-800 rounded-lg border border-neutral-800">
          {skills.map((s) => (
            <li key={s.id} className="px-4 py-3">
              <span className="font-medium">{s.name}</span>
              <span className="ml-2 text-xs text-neutral-500">
                {s.is_public ? "public" : "private"}
                {s.security_validated ? " · validated" : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
