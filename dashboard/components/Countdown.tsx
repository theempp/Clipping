"use client";
import { useState } from "react";
import { mmss, openSubmissions, secondsLeft } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { Ring } from "./Charts";
import { Icon } from "./Icon";

const WINDOW_S = 1800;

/** Content Rewards: the post is live, Zo has 30 minutes to submit the link by hand (D025). Broadcast ring. */
export function Countdown() {
  const { snap, markSubmitted } = useStore();
  const now = useNow(1000);
  const [copied, setCopied] = useState(false);
  const open = openSubmissions(snap.submissions, now);
  const s = open[0];
  const left = s ? secondsLeft(s, now) : 0;
  const clip = s ? snap.clips.find((c) => snap.publications.some((p) => p.id === s.publication_id && p.clip_id === c.id)) : undefined;
  const copy = async () => {
    if (!s) return;
    try { await navigator.clipboard.writeText(s.post_url); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard blocked */ }
  };
  return (
    <section aria-label="Content Rewards submit window">
      <div className="sec first"><h2>Submit window</h2><span>{open.length > 1 ? `+${open.length - 1} more open` : "Content Rewards"}</span></div>
      <div className="glass" style={{ textAlign: "center" }}>
        <Ring pct={s ? (left / WINDOW_S) * 100 : 0} size={170} w={10} color={left < 300 ? "var(--bad)" : "var(--warn)"}
          text={s ? `${Math.ceil(left / 60)} min` : "—"} label={s ? `${mmss(left)} left to submit` : "No submission open"} />
        <div className="num" style={{ marginTop: 12, fontSize: 40 }}>{s ? mmss(left) : "--:--"}</div>
        <p className="quiet">{s ? `left to submit${clip?.title ? ` “${clip.title}”` : ""}` : "Starts when a clip goes live on X or Shorts."}</p>
        {s && (
          <div className="chips" style={{ justifyContent: "center", marginTop: 10 }}>
            <button type="button" className="b" onClick={() => void copy()}><Icon name="copy" size={14} /> {copied ? "Copied" : "Copy link"}</button>
            <a className="b" href={s.post_url} target="_blank" rel="noreferrer noopener"><Icon name="external" size={14} /> Open</a>
            <button type="button" className="b ok" onClick={() => void markSubmitted(s.id)}><Icon name="check" size={14} /> Submitted</button>
          </div>
        )}
      </div>
    </section>
  );
}
