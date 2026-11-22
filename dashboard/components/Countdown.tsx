"use client";
import { useState, type CSSProperties } from "react";
import { mmss, openSubmissions, secondsLeft } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { Icon } from "./Icon";

const WINDOW_S = 1800;

/** Content Rewards: the post is live, Zo has 30 minutes to submit the link by hand (D025). */
export function Countdown({ variant = "card" }: { variant?: "card" | "dial" }) {
  const { snap, markSubmitted } = useStore();
  const now = useNow(1000);
  const [copied, setCopied] = useState(false);
  const open = openSubmissions(snap.submissions, now);
  const s = open[0];
  const left = s ? secondsLeft(s, now) : 0;
  const urgent = !!s && left < 5 * 60;
  const host = s ? (() => { try { return new URL(s.post_url).hostname.replace(/^www\./, ""); } catch { return "post"; } })() : "";
  const copy = async () => {
    if (!s) return;
    try { await navigator.clipboard.writeText(s.post_url); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard blocked */ }
  };
  const t = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

  // Ticks and the time are both drawn in one SVG, so nothing stacks on top of anything else.
  const dial = (size: number) => {
    const frac = s ? left / WINDOW_S : 0;
    return (
      <svg viewBox="0 0 176 176" width={size} height={size} className={`dial${urgent ? " urgent" : ""}`}
        role="img" aria-label={s ? `${mmss(left)} left to submit` : "No submission open"}>
        {Array.from({ length: 60 }, (_, i) => {
          const a = (i / 60) * Math.PI * 2 - Math.PI / 2;
          const r1 = i % 5 === 0 ? 68 : 73;
          return <line key={i} x1={88 + Math.cos(a) * r1} y1={88 + Math.sin(a) * r1}
            x2={88 + Math.cos(a) * 80} y2={88 + Math.sin(a) * 80} className={i / 60 < frac ? "on" : ""}
            style={{ "--t": (i / 60).toFixed(3) } as CSSProperties} />;
        })}
        <text x="88" y="92" textAnchor="middle" className="dt">{s ? mmss(left) : "--:--"}</text>
        <text x="88" y="114" textAnchor="middle" className="ds">{s ? "to submit" : "nothing open"}</text>
      </svg>
    );
  };

  if (variant === "dial") {
    return (
      <section className="card dialc" aria-label="Content Rewards countdown">
        <div className="card-h"><h2>Submit window</h2>{open.length > 1 && <span className="lbl">+{open.length - 1} more</span>}</div>
        {dial(150)}
        {s ? (
          <div className="dial-act">
            <button type="button" className="btn sm" onClick={() => void copy()}><Icon name="copy" /> {copied ? "Copied" : "Copy link"}</button>
            <button type="button" className="btn sm light" onClick={() => void markSubmitted(s.id)}>Submitted</button>
          </div>
        ) : <p className="quiet">Starts when a clip goes live.</p>}
      </section>
    );
  }

  return (
    <section className={`card cr${urgent ? " urgent" : ""}`} aria-label="Content Rewards">
      <div className="card-h">
        <h2>Content Rewards</h2>
        {open.length > 1 ? <span className="lbl">+{open.length - 1} more open</span> : <span className="lbl">30 min window</span>}
      </div>
      {s ? (
        <div className="cr-b">
          {dial(108)}
          <div className="cr-t">
            <b>Posted on {host}</b>
            <span>{t(s.posted_at)} · closes {t(s.deadline_at)}</span>
            <div className="cr-act">
              <button type="button" className="btn sm" onClick={() => void copy()}><Icon name="copy" /> {copied ? "Copied" : "Copy"}</button>
              <a className="btn sm" href={s.post_url} target="_blank" rel="noreferrer noopener"><Icon name="external" /> Open</a>
              <button type="button" className="btn sm light" onClick={() => void markSubmitted(s.id)}><Icon name="check" /> Submitted</button>
            </div>
          </div>
        </div>
      ) : (
        <p className="quiet">No post waiting. When a clip goes live on X or Shorts, its 30-minute submit window starts here.</p>
      )}
    </section>
  );
}
