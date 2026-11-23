"use client";
import { useState } from "react";
import { PC_NAME } from "@/lib/env";
import { ago, pcState } from "@/lib/logic";
import { isAdminView } from "@/lib/pods";
import { useNow, useStore } from "@/lib/store";

const LABEL = {
  offline: "offline", waking: "waking up", watching: "watching", idle: "awake, no one live",
  sleeping: "going to sleep", asleep: "asleep",
} as const;

/** Wake Up (D014/D055). The whole card is the switch; the small line is what the PC itself reports.
 *  Flipping it on lights the page up (Shell runs the sweep). */
export function WakeToggle({ compact = false }: { compact?: boolean }) {
  const { snap, setAwake, podsOn, access } = useStore();
  const now = useNow(1000);
  const [busy, setBusy] = useState(false);
  const want = snap.control.awake;
  const st = pcState(snap.heartbeat, want, now);
  const live = st === "watching" ? snap.heartbeat?.status.live?.length ?? 0 : 0;
  const detail = st === "offline"
    ? snap.heartbeat ? `${PC_NAME} seen ${ago(snap.heartbeat.seen_at, now)}` : `${PC_NAME} never seen`
    : st === "watching" ? `Awake · watching ${live} live` : `${want ? "Awake" : "Asleep"} · ${LABEL[st]}`;
  const flip = async () => {
    if (busy) return;
    setBusy(true);
    try { await setAwake(!want); } finally { setBusy(false); }
  };
  if (!isAdminView(podsOn, access)) return null;
  return (
    <button type="button" role="switch" aria-checked={want} aria-busy={busy}
      aria-label={want ? `${PC_NAME} is awake. Put it to sleep` : `${PC_NAME} is asleep. Wake it up`}
      className={`glass wake${compact ? " compact" : ""} pc-${st}`} onClick={() => void flip()}>
      <span className={`sw${want ? " on" : ""}`} aria-hidden="true" />
      <span>
        <b>Wake Up</b>
        {!compact && <small>{detail}</small>}
      </span>
    </button>
  );
}

/** Shown on every page while the PC is told to sleep: one big, obvious way to wake it (admin only, D108; others see the notice). */
export function SleepBanner() {
  const { snap, setAwake, podsOn, access } = useStore();
  const now = useNow(5000);
  const [busy, setBusy] = useState(false);
  const st = pcState(snap.heartbeat, false, now);
  return (
    <section className="glass sleep" aria-label={`${PC_NAME} is asleep`}>
      <div className="tx">
        <b>{PC_NAME} is asleep</b>
        <span>No streams are being watched or clipped. Review, the library and live numbers still work.
          {st === "offline" ? ` PC ${snap.heartbeat ? `last seen ${ago(snap.heartbeat.seen_at, now)}` : "has not reported yet"}.` : ""}</span>
      </div>
      {isAdminView(podsOn, access) && (
        <button type="button" className="b acc lg" disabled={busy}
          onClick={async () => { setBusy(true); try { await setAwake(true); } finally { setBusy(false); } }}>
          {busy ? "Waking…" : "Wake up"}
        </button>
      )}
    </section>
  );
}
