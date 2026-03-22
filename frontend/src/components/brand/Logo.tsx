import Link from "next/link";

export function Logo({ size = "md" }: { size?: "sm" | "md" }) {
  const iconSize = size === "sm" ? "text-xl" : "text-2xl";
  const textSize = size === "sm" ? "text-sm" : "text-lg";

  return (
    <Link href="/" className="flex items-center gap-2">
      <span
        className={`material-symbols-outlined ${iconSize} text-af-primary`}
        style={{ fontVariationSettings: "'FILL' 1" }}
      >
        token
      </span>
      <span className={`font-mono ${textSize} font-bold tracking-tighter text-white`}>
        AgentForge
      </span>
    </Link>
  );
}
