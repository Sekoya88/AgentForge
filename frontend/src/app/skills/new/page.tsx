"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, api } from "@/lib/api";

export default function NewSkillPage() {
  const router = useRouter();
  const [name, setName] = useState("echo_tool");
  const [source, setSource] = useState('def run(x: str) -> str:\n    return x\n');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api("/api/v1/skills", {
        method: "POST",
        body: JSON.stringify({
          name,
          source_code: source,
          parameters_schema: {},
          permissions: ["read"],
          is_public: false,
        }),
      });
      router.push("/skills");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.push("/login");
      else setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <Link href="/skills" className="text-sm text-neutral-500 hover:text-white">
        ← Skills
      </Link>
      <h1 className="text-2xl font-semibold">New skill</h1>
      <label className="block text-sm text-neutral-400">Name</label>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="w-full max-w-lg rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
      />
      <label className="block text-sm text-neutral-400">Source (Python stub)</label>
      <textarea
        value={source}
        onChange={(e) => setSource(e.target.value)}
        rows={8}
        className="w-full max-w-2xl rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 font-mono text-sm"
      />
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button
        type="button"
        disabled={busy}
        onClick={submit}
        className="rounded-md bg-cyan-500 px-4 py-2 text-sm font-medium text-black disabled:opacity-50"
      >
        {busy ? "Saving…" : "Create"}
      </button>
    </div>
  );
}
