"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE, buildAuthHeaders } from "@/lib/api";

type VoiceExecResponse = {
  status?: string;
  output_audio_b64?: string | null;
  output_messages?: { role: string; content: string }[] | null;
  duration_ms?: number | null;
  detail?: string;
};

type Turn = {
  id: number;
  transcript: string | null;
  reply: string | null;
  audioB64: string | null;
  error: string | null;
};

// ── Waveform bars animation ───────────────────────────────────────────────────

function RecordingWave() {
  return (
    <div className="flex items-end justify-center gap-0.5" style={{ height: "2rem" }}>
      {[0.4, 0.7, 1, 0.8, 0.5, 0.9, 0.6, 1, 0.7, 0.4].map((h, i) => (
        <div
          key={i}
          className="w-1 rounded-full bg-red-400"
          style={{
            height: `${h * 100}%`,
            animation: `wavebar 0.8s ease-in-out infinite alternate`,
            animationDelay: `${i * 80}ms`,
          }}
        />
      ))}
      <style>{`
        @keyframes wavebar {
          from { transform: scaleY(0.3); }
          to   { transform: scaleY(1); }
        }
      `}</style>
    </div>
  );
}

// ── VoiceChatPanel ────────────────────────────────────────────────────────────

export function VoiceTestButton({ agentId }: { agentId: string }) {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [open, setOpen] = useState(false);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const turnIdRef = useRef(0);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (open) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [turns, open]);

  const startRecording = async () => {
    setErr(null);
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

  const stopRecording = () => {
    recorderRef.current?.stop();
    setRecording(false);
  };

  const sendRecording = async () => {
    setBusy(true);
    const turnId = ++turnIdRef.current;
    const pendingTurn: Turn = { id: turnId, transcript: null, reply: null, audioB64: null, error: null };
    setTurns((prev) => [...prev, pendingTurn]);

    try {
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      const form = new FormData();
      form.append("file", blob, "recording.webm");
      form.append("input_messages", JSON.stringify([{ role: "user", content: "" }]));

      const res = await fetch(`${API_BASE}/api/v1/agents/${agentId}/execute/audio`, {
        method: "POST",
        headers: buildAuthHeaders(),
        body: form,
      });

      const text = await res.text();
      let body: VoiceExecResponse | null = null;
      try { body = text ? (JSON.parse(text) as VoiceExecResponse) : null; } catch { /* */ }

      if (!res.ok) {
        const detail = body && "detail" in body
          ? String((body as { detail: unknown }).detail)
          : text || res.statusText;
        setTurns((prev) =>
          prev.map((t) => (t.id === turnId ? { ...t, error: detail } : t)),
        );
        return;
      }

      // Extract transcript (user ASR output) and reply (LLM output)
      const msgs = body?.output_messages ?? [];
      const userMsg = msgs.find((m) => m.role === "user");
      const aiMsg = [...msgs].reverse().find((m) => m.role === "assistant");

      const transcript = typeof userMsg?.content === "string" ? userMsg.content : null;
      const reply = typeof aiMsg?.content === "string" ? aiMsg.content : null;
      const audioB64 = body?.output_audio_b64 ?? null;

      setTurns((prev) =>
        prev.map((t) =>
          t.id === turnId ? { ...t, transcript, reply, audioB64 } : t,
        ),
      );

      // Auto-play audio response
      if (audioB64) {
        const src = `data:audio/mp3;base64,${audioB64}`;
        if (audioRef.current) {
          audioRef.current.pause();
          audioRef.current.src = "";
        }
        const audio = new Audio(src);
        audioRef.current = audio;
        setPlaying(true);
        audio.onended = () => setPlaying(false);
        audio.onerror = () => setPlaying(false);
        void audio.play().catch(() => setPlaying(false));
      }
    } catch (e) {
      setTurns((prev) =>
        prev.map((t) =>
          t.id === turnId ? { ...t, error: e instanceof Error ? e.message : "Upload failed" } : t,
        ),
      );
    } finally {
      setBusy(false);
      recorderRef.current = null;
      chunksRef.current = [];
    }
  };

  const stopAudio = () => {
    audioRef.current?.pause();
    setPlaying(false);
  };

  const clearHistory = () => {
    stopAudio();
    setTurns([]);
    setErr(null);
  };

  const handleMicClick = () => {
    if (recording) stopRecording();
    else void startRecording();
  };

  const hasVoice = turns.length > 0 || recording || busy;

  return (
    <div className="w-full">
      {/* Collapsed trigger */}
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex items-center gap-2 rounded-lg border border-af-border/60 bg-af-surface-high px-4 py-2 text-sm text-af-on-surface transition-colors hover:border-af-primary/60 hover:text-af-primary"
        >
          <span className="material-symbols-outlined text-sm">mic</span>
          Voice conversation
        </button>
      )}

      {/* Panel */}
      {open && (
        <div className="overflow-hidden rounded-xl border border-af-border/60 bg-af-surface-void/80">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-af-border/40 px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-sm text-af-primary">mic</span>
              <span className="text-xs font-bold uppercase tracking-widest text-af-muted-dim">
                Voice conversation
              </span>
              {playing && (
                <span className="flex items-center gap-1 text-[10px] text-af-tertiary">
                  <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-af-tertiary" />
                  Playing…
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {hasVoice && (
                <button
                  type="button"
                  onClick={clearHistory}
                  className="text-[10px] text-af-muted-dim hover:text-af-error"
                >
                  Clear
                </button>
              )}
              <button
                type="button"
                onClick={() => { stopAudio(); setOpen(false); }}
                className="text-af-muted-dim hover:text-af-on-surface"
              >
                <span className="material-symbols-outlined text-sm">close</span>
              </button>
            </div>
          </div>

          {/* Conversation transcript */}
          <div className="max-h-72 min-h-[4rem] overflow-y-auto px-4 py-3">
            {turns.length === 0 && !recording && !busy && (
              <p className="text-center text-xs text-af-muted-dim">
                Press the mic button and speak — the agent will reply with audio.
              </p>
            )}
            <div className="flex flex-col gap-3">
              {turns.map((turn) => (
                <div key={turn.id} className="flex flex-col gap-1.5">
                  {/* User transcript */}
                  {turn.transcript !== null && turn.transcript !== "" && (
                    <div className="flex justify-end">
                      <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-af-primary px-3 py-2 text-sm text-black">
                        {turn.transcript}
                      </div>
                    </div>
                  )}
                  {turn.transcript === "" && (
                    <div className="flex justify-end">
                      <div className="max-w-[80%] rounded-2xl rounded-br-sm border border-af-border/40 bg-af-surface-high px-3 py-2 text-xs text-af-muted-dim italic">
                        (no transcription — check OpenAI key)
                      </div>
                    </div>
                  )}

                  {/* AI reply */}
                  {turn.reply !== null && (
                    <div className="flex items-start gap-2">
                      <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-af-primary/30 bg-af-primary/10">
                        <span className="material-symbols-outlined text-xs text-af-primary">smart_toy</span>
                      </div>
                      <div className="max-w-[80%] rounded-2xl rounded-bl-sm border border-af-border/60 bg-af-surface-high px-3 py-2 text-sm text-af-on-surface">
                        {turn.reply}
                        {turn.audioB64 && (
                          <audio
                            controls
                            src={`data:audio/mp3;base64,${turn.audioB64}`}
                            className="mt-2 h-7 w-full"
                            preload="metadata"
                          />
                        )}
                      </div>
                    </div>
                  )}

                  {/* Error */}
                  {turn.error && (
                    <div className="rounded-lg border border-af-error/30 bg-af-error/10 px-3 py-2 text-xs text-af-error">
                      {turn.error}
                    </div>
                  )}

                  {/* Pending (sent but not yet replied) */}
                  {!turn.reply && !turn.error && turn.transcript === null && (
                    <div className="flex items-start gap-2">
                      <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-af-primary/30 bg-af-primary/10">
                        <span className="material-symbols-outlined text-xs text-af-primary">smart_toy</span>
                      </div>
                      <div className="flex items-center gap-1.5 rounded-2xl border border-af-border/60 bg-af-surface-high px-3 py-2">
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-af-muted [animation-delay:0ms]" />
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-af-muted [animation-delay:150ms]" />
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-af-muted [animation-delay:300ms]" />
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {/* Recording state in the transcript */}
              {recording && (
                <div className="flex justify-end">
                  <div className="flex items-center gap-2 rounded-2xl rounded-br-sm bg-red-500/20 px-3 py-2 text-sm text-red-300">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-red-400" />
                    Recording…
                  </div>
                </div>
              )}
            </div>
            <div ref={bottomRef} />
          </div>

          {/* Controls */}
          <div className="flex items-center justify-center gap-4 border-t border-af-border/40 px-4 py-4">
            {err && (
              <p className="mr-auto text-xs text-af-error">{err}</p>
            )}

            {/* Stop audio button */}
            {playing && (
              <button
                type="button"
                onClick={stopAudio}
                title="Stop audio"
                className="flex h-9 w-9 items-center justify-center rounded-full border border-af-tertiary/40 bg-af-tertiary/10 text-af-tertiary transition-colors hover:bg-af-tertiary/20"
              >
                <span className="material-symbols-outlined text-base">stop_circle</span>
              </button>
            )}

            {/* Waveform while recording */}
            {recording && (
              <div className="flex-1 px-2">
                <RecordingWave />
              </div>
            )}

            {/* Mic button */}
            <button
              type="button"
              disabled={busy}
              onClick={handleMicClick}
              title={recording ? "Stop & send" : "Start recording"}
              className={`relative flex h-16 w-16 items-center justify-center rounded-full border-2 text-white transition-all disabled:opacity-50 ${
                recording
                  ? "border-red-500 bg-red-500 shadow-[0_0_24px_rgba(239,68,68,0.5)]"
                  : "border-af-primary bg-af-primary shadow-[0_0_16px_rgba(195,192,255,0.3)] hover:shadow-[0_0_24px_rgba(195,192,255,0.5)]"
              }`}
            >
              {busy ? (
                <span className="h-6 w-6 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : recording ? (
                <span className="material-symbols-outlined text-2xl">stop</span>
              ) : (
                <span className="material-symbols-outlined text-2xl">mic</span>
              )}
              {recording && (
                <span className="absolute inset-0 animate-ping rounded-full border border-red-400 opacity-40" />
              )}
            </button>

            {/* Instruction label */}
            {!recording && !busy && (
              <p className="absolute mt-24 text-[10px] text-af-muted-dim">
                {playing ? "Écoute…" : "Appuie pour parler"}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
