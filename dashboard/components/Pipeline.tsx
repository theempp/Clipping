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

export function PipelineTiles() {
  const steps = usePipeline();
  return (
    <div className="tiles">
      {steps.map((s) => (
        <div key={s.k} className={`tile ${s.n ? "act" : ""}`}>
          <span className="ic"><Icon name={s.icon} /></span>
          <span className="st" />
          <b>{s.label}{s.n ? ` · ${s.n}` : ""}</b>
          <span>{s.sub}</span>
        </div>
      ))}
    </div>
  );
}
