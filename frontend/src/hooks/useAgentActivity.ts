"use client";

import { useCallback, useRef, useState } from "react";
import { AgentStep } from "@/types/chat";

export type InterruptPayload = {
  execution_id: string;
  pending_tools: { tool_name: string; arg: string }[];
};

export type AgentActivity = {
  toasts: AgentStep[];
  steps: AgentStep[];
  isRunning: boolean;
  interrupt: InterruptPayload | null;
};

/**
 * Parses raw SSE events from any agent execution stream and maintains
 * live toast state + accumulated step history.
 *
 * Usage:
 *   const { activity, onLine, reset } = useAgentActivity();
 *   // Pass `onLine` as the callback to consumeForgeSse / consumeExecutionSse
 *   // Read `activity.toasts` for live display, `activity.steps` for chips
 */
export function useAgentActivity() {
  const [activity, setActivity] = useState<AgentActivity>({
    toasts: [],
    steps: [],
    isRunning: false,
    interrupt: null,
  });

  const startTimeRef = useRef<number>(Date.now());
  const stepsAccRef = useRef<AgentStep[]>([]);

  const reset = useCallback(() => {
    startTimeRef.current = Date.now();
    stepsAccRef.current = [];
    setActivity({ toasts: [], steps: [], isRunning: false, interrupt: null });
  }, []);

  const onLine = useCallback((eventName: string, dataJson: string) => {
    let data: Record<string, unknown> = {};
    try { data = JSON.parse(dataJson); } catch { /* ignore */ }

    const now = Date.now();

    switch (eventName) {
      case "agent_start": {
        const label = (data.agent_name as string) ?? (data.node_type as string) ?? "agent";
        const step: AgentStep = { event: "agent_start", label, timestamp: now };
        stepsAccRef.current = [...stepsAccRef.current, step];
        setActivity((prev) => ({
          ...prev,
          isRunning: true,
          toasts: [...prev.toasts, step].slice(-10),
          steps: [...prev.steps, step],
        }));
        break;
      }
      case "tool_call": {
        const label = (data.tool_name as string) ?? "tool";
        const step: AgentStep = { event: "tool_call", label, timestamp: now };
        stepsAccRef.current = [...stepsAccRef.current, step];
        setActivity((prev) => ({
          ...prev,
          toasts: [...prev.toasts, step].slice(-10),
          steps: [...prev.steps, step],
        }));
        break;
      }
      case "tool_result": {
        const label = (data.tool_name as string) ?? "tool";
        // Update matching tool_call step with duration, don't add a new toast
        const innerNow = Date.now();
        const callStep = [...stepsAccRef.current].reverse().find(
          (s) => s.event === "tool_call" && s.label === label
        );
        const durationMs = callStep ? innerNow - callStep.timestamp : undefined;
        stepsAccRef.current = stepsAccRef.current.map((s) =>
          s === callStep ? { ...s, durationMs } : s
        );
        setActivity((prev) => {
          const prevCallStep = [...prev.steps].reverse().find(
            (s) => s.event === "tool_call" && s.label === label
          );
          const updatedSteps = prev.steps.map((s) =>
            s === prevCallStep ? { ...s, durationMs } : s
          );
          return { ...prev, steps: updatedSteps };
        });
        break;
      }
      case "interrupt": {
        const payload: InterruptPayload = {
          execution_id: (data.execution_id as string) ?? "",
          pending_tools: (data.pending_tools as InterruptPayload["pending_tools"]) ?? [],
        };
        setActivity((prev) => ({ ...prev, interrupt: payload }));
        break;
      }
      case "complete":
      case "done":
      case "completed": {
        const durationMs = now - startTimeRef.current;
        const doneStep: AgentStep = { event: "complete", label: "done", durationMs, timestamp: now };
        stepsAccRef.current = [...stepsAccRef.current, doneStep];
        // Dismiss toasts after a short delay (handled in AgentToastStack via isRunning=false)
        setActivity((prev) => ({
          ...prev,
          isRunning: false,
          interrupt: null,
          steps: [...prev.steps, doneStep],
          toasts: [], // clear live toasts
        }));
        break;
      }
      case "error": {
        const errStep: AgentStep = { event: "error", label: (data.message as string) ?? (data.detail as string) ?? "error", timestamp: now };
        stepsAccRef.current = [...stepsAccRef.current, errStep];
        setActivity((prev) => ({
          ...prev,
          isRunning: false,
          toasts: [],
          steps: [...prev.steps, errStep],
        }));
        break;
      }
      default:
        break;
    }
  }, []);

  return { activity, onLine, reset, stepsRef: stepsAccRef };
}
