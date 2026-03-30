"use client";

import { useRef, useState } from "react";
import { API_BASE, buildAuthHeaders } from "@/lib/api";
import { ExecutionLog } from "@/components/execution/ExecutionLog";

type LogLine = { event: string; data: string; at: number };

type VoiceExecResponse = {
  status?: string;
  output_audio_b64?: string | null;
  output_messages?: { role: string; content: string }[] | null;
  duration_ms?: number | null;
  detail?: string;
};

export function VoiceTestButton({ agentId }: { agentId: string }) {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<LogLine[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const start = async () => {
    setErr(null);
    setLog([]);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        void sendRecording();
      };
      recorder.start();
      setRecording(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Microphone access denied");
    }
  };

  const sendRecording = async () => {
    setBusy(true);
    setRecording(false);
    try {
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      const form = new FormData();
      form.append("file", blob, "recording.webm");
      form.append(
        "input_messages",
        JSON.stringify([{ role: "user", content: "" }]),
      );
      const res = await fetch(
        `${API_BASE}/api/v1/agents/${agentId}/execute/audio`,
        {
          method: "POST",
          headers: buildAuthHeaders(),
          body: form,
        },
      );
      const text = await res.text();
      let body: VoiceExecResponse | null = null;
      try {
        body = text ? (JSON.parse(text) as VoiceExecResponse) : null;
      } catch {
        body = null;
      }
      if (!res.ok) {
        let detail = text || res.statusText;
        if (body && typeof body === "object" && "detail" in body) {
          const d = (body as { detail: unknown }).detail;
          detail = Array.isArray(d) ? JSON.stringify(d) : String(d);
        }
        setLog((prev) => [
          ...prev,
          { event: "error", data: detail, at: Date.now() },
        ]);
        return;
      }
      if (!body) {
        setLog((prev) => [
          ...prev,
          { event: "error", data: "Empty response", at: Date.now() },
        ]);
        return;
      }
      setLog((prev) => [
        ...prev,
        {
          event: "result",
          data: JSON.stringify({
            status: body!.status,
            duration_ms: body!.duration_ms,
          }),
          at: Date.now(),
        },
      ]);
      const msgs = body.output_messages ?? [];
      const last = msgs[msgs.length - 1];
      if (last?.content) {
        setLog((prev) => [
          ...prev,
          {
            event: "transcript",
            data:
              typeof last.content === "string"
                ? last.content
                : JSON.stringify(last.content),
            at: Date.now(),
          },
        ]);
      }
      if (body.output_audio_b64) {
        setLog((prev) => [
          ...prev,
          {
            event: "audio",
            data: JSON.stringify({ audio_b64: body.output_audio_b64 }),
            at: Date.now(),
          },
        ]);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
      recorderRef.current = null;
      chunksRef.current = [];
    }
  };

  const stop = () => {
    recorderRef.current?.stop();
    setRecording(false);
  };

  return (
    <div className="space-y-2">
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          if (recording) stop();
          else void start();
        }}
        className={`rounded-lg border px-3 py-1.5 text-xs font-bold transition-colors disabled:opacity-50 ${
          recording
            ? "border-red-500 text-red-400 hover:bg-red-500/10"
            : "border-af-border text-af-on-surface hover:border-af-primary hover:text-af-primary"
        }`}
      >
        {busy
          ? "Sending…"
          : recording
            ? "Stop & send"
            : "Test voice (mic)"}
      </button>
      {err && <p className="text-xs text-af-error">{err}</p>}
      {log.length > 0 && <ExecutionLog lines={log} />}
    </div>
  );
}
