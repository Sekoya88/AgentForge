"use client";

import { useCallback, useEffect, useState } from "react";
import {
  approveProposal,
  countPendingProposals,
  listProposals,
  rejectProposal,
  type Proposal,
} from "@/lib/proposals-api";

export function useProposals() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [list, cnt] = await Promise.all([listProposals(), countPendingProposals()]);
      setProposals(list);
      setCount(cnt);
    } catch {
      // silently fail — badge disappears, doesn't break Forge
    }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = setInterval(() => void refresh(), 60_000);
    return () => clearInterval(interval);
  }, [refresh]);

  const approve = useCallback(
    async (id: string) => {
      setLoading(true);
      try {
        await approveProposal(id);
        await refresh();
      } finally {
        setLoading(false);
      }
    },
    [refresh],
  );

  const reject = useCallback(
    async (id: string) => {
      setLoading(true);
      try {
        await rejectProposal(id);
        await refresh();
      } finally {
        setLoading(false);
      }
    },
    [refresh],
  );

  return { proposals, count, loading, approve, reject, refresh };
}
