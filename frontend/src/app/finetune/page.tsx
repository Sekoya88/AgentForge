"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";

type Job = {
  id: string;
  base_model: string;
  status: string;
  inference_endpoint: string | null;
};

export default function FinetunePage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const data = await api<Job[]>("/api/v1/finetune");
        if (!c) setJobs(data);
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
        <h1 className="text-2xl font-semibold">Fine-tune jobs</h1>
        <Link
          href="/finetune/new"
          className="rounded-md bg-cyan-500 px-3 py-1.5 text-sm font-medium text-black"
        >
          New job
        </Link>
      </div>
      {error && <p className="text-sm text-amber-400">{error}</p>}
      {jobs && jobs.length === 0 && <p className="text-neutral-500">No jobs yet (Modal integration pending).</p>}
      {jobs && jobs.length > 0 && (
        <ul className="divide-y divide-neutral-800 rounded-lg border border-neutral-800">
          {jobs.map((j) => (
            <li key={j.id} className="px-4 py-3">
              <span className="font-medium">{j.base_model}</span>
              <p className="text-xs text-neutral-500">
                {j.status}
                {j.inference_endpoint ? ` · ${j.inference_endpoint}` : ""}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
