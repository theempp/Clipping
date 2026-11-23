"use client";
import { pcState } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";

type Agent = { k: string; label: string; sub: string; n: number; tone: "run" | "warn" | "ok" | "" };

/** Worker stages straight from the PC heartbeat (queue depth per local stage), as the Broadcast agent ticker. */
export function useAgents(): Agent[] {
  const { snap } = useStore();
  const now = useNow(5000);
  const st = pcState(snap.heartbeat, snap.control.awake, now);
  const up = st !== "offline";
  const q = up ? snap.heartbeat?.status.queue ?? {} : {};
  const live = up ? snap.heartbeat?.status.live ?? [] : [];
  const names = live.map((k) => k.split(":")[1]).join(", ");
  const hasGrok = snap.spend.some((s) => s.kind === "grok");
  const qa = snap.clips.slice(0, 5);
  const qaOk = qa.filter((c) => c.qa?.passed !== false).length;
  const n = (x?: number) => x ?? 0;
  return [
    { k: "watch", label: "Watch", n: live.length, sub: live.length ? `${names}` : up ? "no one live" : "PC offline", tone: live.length ? "run" : "" },
    { k: "detect", label: "Detect", n: n(q.detected) + n(q.captured), sub: `${n(q.detected) + n(q.captured)} windows in line`, tone: n(q.detected) + n(q.captured) ? "run" : "" },
    { k: "trans", label: "Transcribe", n: n(q.transcribed), sub: "whisperX", tone: n(q.transcribed) ? "run" : "" },
    { k: "judge", label: "Judge", n: n(q.judged), sub: hasGrok ? "Grok" : "Grok key not added yet", tone: hasGrok ? (n(q.judged) ? "run" : "") : "warn" },
    { k: "render", label: "Render", n: n(q.rendered) + n(q.qa_passed), sub: "9:16 + captions", tone: n(q.rendered) + n(q.qa_passed) ? "run" : "" },
    { k: "qa", label: "QA", n: 0, sub: qa.length ? `last ${qa.length}: ${qaOk} passed` : "nothing yet", tone: qa.length && qaOk === qa.length ? "ok" : qa.length ? "warn" : "" },
  ];
}

const PILL = { run: "running", warn: "waiting", ok: "idle ok", "": "idle" } as const;

export function AgentTicker() {
  const agents = useAgents();
  return (
    <div className="ticker" role="list" aria-label="Agents">
      {agents.map((a) => (
        <div key={a.k} className="agent" role="listitem">
          <span className={`dotst ${a.tone}`} />
          <div><b>{a.label}</b><small>{a.sub}</small></div>
          <span className={`pill ${a.tone}`}>{PILL[a.tone]}</span>
        </div>
      ))}
    </div>
  );
}
