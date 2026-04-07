import { useEffect, useState } from "react";

/**
 * Returns true if the message is actively streaming AND more than 300ms have
 * passed since the last token arrived (i.e., a "thinking" gap is in progress).
 * Polls every 100ms. Immediately returns false when not streaming.
 */
export function useStreamingGap(isStreaming: boolean, lastTokenAt?: number): boolean {
  const [gap, setGap] = useState(false);

  useEffect(() => {
    if (!isStreaming) {
      setGap(false);
      return;
    }

    const id = setInterval(() => {
      if (lastTokenAt === undefined) {
        setGap(false);
        return;
      }
      setGap(Date.now() - lastTokenAt > 300);
    }, 100);

    return () => clearInterval(id);
  }, [isStreaming, lastTokenAt]);

  return gap;
}
