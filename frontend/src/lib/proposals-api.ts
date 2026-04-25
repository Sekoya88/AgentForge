import { api } from "@/lib/api";

export interface Proposal {
  id: string;
  proposal_type: string;
  title: string;
  body: string;
  status: string;
  source: string;
  created_at: string;
  agent_id: string | null;
  skill_id: string | null;
}

export async function listProposals(): Promise<Proposal[]> {
  return api<Proposal[]>("/api/v1/proposals");
}

export async function countPendingProposals(): Promise<number> {
  const data = await api<{ count: number }>("/api/v1/proposals/count");
  return data.count;
}

export async function approveProposal(id: string): Promise<void> {
  await api(`/api/v1/proposals/${id}/approve`, { method: "POST" });
}

export async function rejectProposal(id: string): Promise<void> {
  await api(`/api/v1/proposals/${id}/reject`, { method: "POST" });
}
