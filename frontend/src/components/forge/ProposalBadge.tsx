"use client";

interface ProposalBadgeProps {
  count: number;
  onClick: () => void;
}

export function ProposalBadge({ count, onClick }: ProposalBadgeProps) {
  if (count === 0) return null;

  return (
    <button
      type="button"
      onClick={onClick}
      className="relative flex items-center gap-2 rounded-lg border border-yellow-400/30 bg-yellow-400/10 px-3 py-1.5 text-sm font-medium text-yellow-300 transition-colors hover:bg-yellow-400/20"
    >
      <span>Propositions</span>
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-yellow-400 text-xs font-bold text-black">
        {count > 9 ? "9+" : count}
      </span>
    </button>
  );
}
