"use client";
import { PC_NAME } from "@/lib/env";
import { ago, pcState } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";

const LABEL = {
  offline: "offline", waking: "waking up", watching: "watching", idle: "awake", sleeping: "going to sleep",
} as const;

/** Wake Up (D014/D055). The switch shows what Zo asked for; the line under it is what the PC reports. */
export function WakeToggle({ compact = false }: { compact?: boolean }) {
  const { snap, setAwake } = useStore();
  const now = useNow(1000);
  const want = snap.control.awake;
  const st = pcState(snap.heartbeat, want, now);
  const detail = st === "offline"
    ? snap.heartbeat ? `seen ${ago(snap.heartbeat.seen_at, now)}` : "never seen"
    : LABEL[st];
  return (
    <div className={`wake ${compact ? "compact" : ""}`}>
      <div className="wake-txt">
        <b>{PC_NAME} {want ? "awake" : "asleep"}</b>
        {!compact && <small className={`pc-${st}`}>{detail}</small>}
      </div>
      <button type="button" role="switch" aria-checked={want} aria-label="Wake Up"
        className={`tog ${want ? "on" : ""}`} onClick={() => void setAwake(!want)}>
        <i />
      </button>
    </div>
  );
}
