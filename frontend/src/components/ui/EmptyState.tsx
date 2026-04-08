import Link from "next/link";

interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: {
    label: string;
    href: string;
  };
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="af-motion-fade-in flex min-h-[320px] flex-col items-center justify-center rounded-xl border border-dashed border-af-border/60 bg-af-surface-container/20 p-12 text-center shadow-inner">
      <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-full border border-af-border/80 bg-af-surface-high text-af-muted">
        {icon}
      </div>
      <h3 className="mb-2 text-lg font-bold text-af-on-surface">{title}</h3>
      <p className="mb-6 max-w-sm text-sm leading-relaxed text-af-muted">{description}</p>
      {action && (
        <Link href={action.href} className="af-btn-primary px-6 py-2.5 text-sm">
          {action.label}
        </Link>
      )}
    </div>
  );
}
