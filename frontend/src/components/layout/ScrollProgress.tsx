"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

// Thin gradient progress bar at the very top of the viewport.
// Only visible on scrollable pages (hidden when scroll = 0 or 100%).

export function ScrollProgress() {
  const barRef = useRef<HTMLDivElement>(null);
  const pathname = usePathname();

  useEffect(() => {
    const bar = barRef.current;
    if (!bar) return;

    let rafId = 0;

    function update() {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      const progress = docHeight > 0 ? Math.min(scrollTop / docHeight, 1) : 0;

      if (bar) {
        bar.style.transform = `scaleX(${progress})`;
        bar.style.opacity = progress > 0.005 && progress < 0.998 ? "1" : "0";
      }
    }

    function onScroll() {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(update);
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    update(); // initial state

    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(rafId);
    };
  }, [pathname]); // reset on route change

  return (
    <div
      ref={barRef}
      className="pointer-events-none fixed top-0 left-0 z-[100] h-[2px] w-full origin-left opacity-0 transition-opacity duration-200"
      style={{
        background: "linear-gradient(90deg, #4F46E5, #7C3AED, #2DD4BF)",
        boxShadow: "0 0 8px rgba(124,58,237,0.6)",
      }}
      aria-hidden
    />
  );
}
