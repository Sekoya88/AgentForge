"use client";

import type { Proposal } from "@/lib/proposals-api";

interface ProposalCardProps {
  proposal: Proposal;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  loading: boolean;
}

const TYPE_LABELS: Record<string, string> = {
  CREATE_SKILL: "Créer un skill",
  UPDATE_SKILL: "Modifier un skill",
  UPDATE_AGENT_PROMPT: "Modifier le prompt",
  CREATE_KNOWLEDGE: "Ajouter une connaissance",
};

export function ProposalCard({ proposal, onApprove, onReject, loading }: ProposalCardProps) {
  return (
    <div className="rounded-xl border border-yellow-400/20 bg-yellow-400/5 p-4">
      <div className="mb-2 flex items-center gap-2">
        <span className="rounded-md bg-yellow-400/20 px-2 py-0.5 text-xs font-semibold text-yellow-300">
          {TYPE_LABELS[proposal.proposal_type] ?? proposal.proposal_type}
        </span>
        <span className="text-xs text-zinc-500">
          {proposal.source === "meta_tick" ? "Auto" : "On-demand"}
        </span>
      </div>

      <h3 className="mb-1 font-semibold text-white">{proposal.title}</h3>

      <p className="mb-3 line-clamp-3 whitespace-pre-line text-sm text-zinc-400">{proposal.body}</p>

      <div className="flex gap-2">
        <button
          type="button"
          disabled={loading}
          onClick={() => onApprove(proposal.id)}
          className="flex-1 rounded-lg bg-green-500/20 px-3 py-1.5 text-sm font-medium text-green-300 transition-colors hover:bg-green-500/30 disabled:opacity-50"
        >
          Approuver
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={() => onReject(proposal.id)}
          className="flex-1 rounded-lg bg-red-500/10 px-3 py-1.5 text-sm font-medium text-red-400 transition-colors hover:bg-red-500/20 disabled:opacity-50"
        >
          Rejeter
        </button>
      </div>
    </div>
  );
}
