import Link from "next/link";

interface EmptyStateAction {
  label: string;
  href?: string;
  onClick?: () => void;
}

interface EmptyStateProps {
  /** Material Symbols icon name, e.g. "hub", "smart_toy", "menu_book" */
  icon: string;
  title: string;
  description: string;
  action?: EmptyStateAction;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="af-motion-fade-in flex min-h-[400px] flex-col items-center justify-center rounded-2xl border-2 border-dashed border-af-primary/30 bg-gradient-to-b from-af-surface-high/60 to-af-surface-container/40 p-16 text-center shadow-[inset_0_0_60px_rgba(79,70,229,0.06)]">
      {/* Icon container — large, glowing, hard to miss */}
      <div className="mb-7 flex h-24 w-24 items-center justify-center rounded-2xl border-2 border-af-primary/40 bg-gradient-to-br from-af-primary/20 to-af-primary/5 shadow-[0_0_40px_rgba(79,70,229,0.25)]">
        <span className="material-symbols-outlined text-5xl text-af-primary">{icon}</span>
      </div>

      <h2 className="mb-3 text-2xl font-black tracking-tight text-af-on-surface">{title}</h2>
      <p className="mb-8 max-w-md text-base leading-relaxed text-af-muted">{description}</p>

      {action && (
        action.href ? (
          <Link
            href={action.href}
            className="af-btn-primary px-8 py-3 text-sm font-bold shadow-[0_0_20px_rgba(79,70,229,0.35)] transition-shadow hover:shadow-[0_0_30px_rgba(79,70,229,0.5)]"
          >
            {action.label}
          </Link>
        ) : (
          <button
            type="button"
            onClick={action.onClick}
            className="af-btn-primary px-8 py-3 text-sm font-bold shadow-[0_0_20px_rgba(79,70,229,0.35)] transition-shadow hover:shadow-[0_0_30px_rgba(79,70,229,0.5)]"
          >
            {action.label}
          </button>
        )
      )}
    </div>
  );
}
