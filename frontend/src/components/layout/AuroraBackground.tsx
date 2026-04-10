export function AuroraBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden" aria-hidden>
      <div className="af-aurora-mesh" />
      {/* Dark theme blobs */}
      <div className="af-aurora-blob af-aurora-drift-a right-[-80px] top-[-80px] h-[700px] w-[700px] bg-af-indigo opacity-[0.11] dark-blob" />
      <div className="af-aurora-blob af-aurora-drift-b left-[-80px] top-[35%] h-[500px] w-[500px] bg-af-secondary opacity-[0.08] dark-blob" />
      <div className="af-aurora-blob af-aurora-drift-c bottom-[-50px] right-[15%] h-[450px] w-[450px] bg-af-teal-glow opacity-[0.07] dark-blob" />
    </div>
  );
}
