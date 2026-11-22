"use client";
import { useState } from "react";
import { PC_NAME } from "@/lib/env";
import { ago, pcState } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { Icon } from "./Icon";

const LABEL = {
  offline: "offline", waking: "waking up", watching: "watching", idle: "awake, no one live",
  sleeping: "going to sleep", asleep: "sleeping",
} as const;

/** Wake Up (D014/D055). The whole pill is the switch; the small line is what the PC itself reports. */
export function WakeToggle({ compact = false }: { compact?: boolean }) {
  const { snap, setAwake } = useStore();
  const now = useNow(1000);
  const [busy, setBusy] = useState(false);
  const want = snap.control.awake;
  const st = pcState(snap.heartbeat, want, now);
  const live = st === "watching" ? snap.heartbeat?.status.live?.length ?? 0 : 0;
  const detail = st === "offline"
    ? snap.heartbeat ? `PC seen ${ago(snap.heartbeat.seen_at, now)}` : "PC never seen"
    : st === "watching" ? `watching ${live} live` : LABEL[st];
  const flip = async () => {
    if (busy) return;
    setBusy(true);
    try { await setAwake(!want); } finally { setBusy(false); }
  };
  return (
    <button type="button" role="switch" aria-checked={want} aria-busy={busy}
      aria-label={want ? `${PC_NAME} is awake. Put it to sleep` : `${PC_NAME} is asleep. Wake it up`}
      title={want ? "Put to sleep" : "Wake up"}
      className={`pwr ${want ? "on" : "off"}${compact ? " compact" : ""} pc-${st}`} onClick={() => void flip()}>
      <span className="pwr-orb" aria-hidden="true"><Icon name="power" /></span>
      <span className="pwr-t">
        <b>{PC_NAME} {want ? "awake" : "asleep"}</b>
        {!compact && <small>{detail}</small>}
      </span>
      {!compact && <span className="pwr-cta" aria-hidden="true">{want ? "Sleep" : "Wake"}</span>}
    </button>
  );
}

/** Shown at the top of every page while the PC is told to sleep: one big, obvious way to wake it. */
export function SleepBanner() {
  const { snap, setAwake } = useStore();
  const now = useNow(5000);
  const [busy, setBusy] = useState(false);
  const st = pcState(snap.heartbeat, false, now);
  return (
    <section className="sleep" aria-label={`${PC_NAME} is asleep`}>
      <div className="sleep-moon" aria-hidden="true"><Icon name="moon" /><i /><i /><i /></div>
      <div className="sleep-t">
        <b>{PC_NAME} is asleep</b>
        <span>No streams are being watched or clipped. Your queue and approved clips still work.
          {st === "offline" ? ` PC ${snap.heartbeat ? `last seen ${ago(snap.heartbeat.seen_at, now)}` : "has not reported yet"}.` : ""}</span>
      </div>
      <button type="button" className="wakebtn" disabled={busy}
        onClick={async () => { setBusy(true); try { await setAwake(true); } finally { setBusy(false); } }}>
        <span className="wb-glow" aria-hidden="true" />
        <span className="wb-in"><Icon name="power" /> {busy ? "Waking…" : "Wake up"}</span>
      </button>
    </section>
  );
}
