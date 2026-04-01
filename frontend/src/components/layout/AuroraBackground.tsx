export function AuroraBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden" aria-hidden>
      <div className="af-aurora-mesh" />
      <div className="af-aurora-blob af-aurora-drift-a right-[-100px] top-[-100px] h-[600px] w-[600px] bg-af-indigo opacity-[0.16]" />
      <div className="af-aurora-blob af-aurora-drift-b left-[-100px] top-[40%] h-[450px] w-[450px] bg-af-secondary opacity-[0.11]" />
      <div className="af-aurora-blob af-aurora-drift-c bottom-0 right-[20%] h-[400px] w-[400px] bg-af-teal-glow opacity-[0.12]" />
    </div>
  );
}
