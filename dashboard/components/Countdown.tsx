"use client";
import { useState } from "react";
import { mmss, openSubmissions, secondsLeft } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { Icon } from "./Icon";

/** Content Rewards: the post is live, Zo has 30 minutes to submit the link by hand (D025). */
export function Countdown({ variant = "card" }: { variant?: "card" | "dial" }) {
  const { snap, markSubmitted } = useStore();
  const now = useNow(1000);
  const [copied, setCopied] = useState(false);
  const open = openSubmissions(snap.submissions, now);
  const s = open[0];
  const left = s ? secondsLeft(s, now) : 0;
  const urgent = s && left < 5 * 60;
  const host = s ? (() => { try { return new URL(s.post_url).hostname.replace(/^www\./, ""); } catch { return "post"; } })() : "";
  const copy = async () => {
    if (!s) return;
    try { await navigator.clipboard.writeText(s.post_url); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard blocked */ }
  };

  if (variant === "dial") {
    const frac = s ? left / 1800 : 0;
    return (
      <div className={`dial ${urgent ? "urgent" : ""}`} aria-label="Content Rewards countdown">
        <svg viewBox="0 0 176 176">
          {Array.from({ length: 60 }, (_, i) => {
            const a = (i / 60) * Math.PI * 2 - Math.PI / 2;
            const r1 = i % 5 === 0 ? 70 : 74;
            return <line key={i} x1={88 + Math.cos(a) * r1} y1={88 + Math.sin(a) * r1}
              x2={88 + Math.cos(a) * 80} y2={88 + Math.sin(a) * 80} className={i / 60 < frac ? "on" : ""} />;
          })}
        </svg>
        <div className="in">
          <b>{s ? mmss(left) : "--:--"}</b>
          <span>{s ? "to submit" : "nothing open"}</span>
        </div>
      </div>
    );
  }

  return (
    <section className="cd cr">
      <div className="h">
        <span>Content Rewards</span>
        {s && <button type="button" className="pill-sm" onClick={() => void markSubmitted(s.id)}>Submitted</button>}
      </div>
      {s ? (
        <div className="bx">
          <div className={`lt ${urgent ? "urgent" : ""}`} aria-live="off">{mmss(left)}</div>
          <div className="rt">
            <b>Posted on {host}</b>
            {new Date(s.posted_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
            {" · closes "}
            {new Date(s.deadline_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
            <div className="cr-act">
              <button type="button" onClick={() => void copy()}><Icon name="copy" /> {copied ? "Copied" : "Copy"}</button>
              <a href={s.post_url} target="_blank" rel="noreferrer noopener">Open</a>
            </div>
          </div>
        </div>
      ) : (
        <p className="quiet">No post waiting. When a clip goes live on X or Shorts, its 30-minute submit window starts here.</p>
      )}
      {open.length > 1 && <p className="more">+{open.length - 1} more open</p>}
    </section>
  );
}
