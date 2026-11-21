"use client";
import { pcState } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { Icon } from "./Icon";

/** Concurrent worker activity, straight from the PC heartbeat (queue depth per local stage). */
export function usePipeline() {
  const { snap } = useStore();
  const now = useNow(5000);
  const st = pcState(snap.heartbeat, snap.control.awake, now);
  const up = st !== "offline";
  const q = up ? snap.heartbeat?.status.queue ?? {} : {};
  const live = up ? snap.heartbeat?.status.live ?? [] : [];
  const names = live.map((k) => k.split(":")[1]).join(", ");
  return [
    { k: "watch", icon: "eye", label: "Watching", n: live.length, sub: live.length ? names : up ? "no one live" : "PC offline" },
    { k: "trans", icon: "text", label: "Transcribing", n: (q.detected ?? 0) + (q.captured ?? 0), sub: "whisperX" },
    { k: "judge", icon: "wave", label: "Judging", n: q.transcribed ?? 0, sub: "Grok" },
    { k: "render", icon: "film", label: "Rendering", n: (q.judged ?? 0) + (q.rendered ?? 0) + (q.qa_passed ?? 0), sub: "ffmpeg + QA" },
  ];
}

/** The four worker stages as one card. `compact` = vertical list for the streamer page side column. */
export function PipelineTiles({ compact = false }: { compact?: boolean }) {
  const steps = usePipeline();
  return (
    <section className={`card pipe${compact ? " compact" : ""}`} aria-label="Pipeline">
      <div className="card-h"><h2>Pipeline</h2><span className="lbl">on the PC</span></div>
      <ol className="steps">
        {steps.map((s) => (
          <li key={s.k} className={s.n ? "act" : ""}>
            <span className="ic"><Icon name={s.icon} /></span>
            <span className="tx"><b>{s.label}</b><span>{s.sub}</span></span>
            <em>{s.n ? (s.k === "watch" ? `${s.n} live` : s.n) : "idle"}</em>
          </li>
        ))}
      </ol>
    </section>
  );
}
