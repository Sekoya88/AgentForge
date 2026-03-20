export function AuroraBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden" aria-hidden>
      <div className="af-aurora-blob right-[-100px] top-[-100px] h-[600px] w-[600px] bg-[#4F46E5] opacity-[0.18]" />
      <div className="af-aurora-blob left-[-100px] top-[40%] h-[500px] w-[500px] bg-[#7C3AED] opacity-[0.15]" />
      <div className="af-aurora-blob bottom-0 right-[20%] h-[400px] w-[400px] bg-[#2DD4BF] opacity-[0.12]" />
    </div>
  );
}
