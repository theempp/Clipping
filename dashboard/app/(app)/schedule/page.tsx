"use client";
import Link from "next/link";
import { ApprovedList } from "@/components/ApprovedList";
import { Countdown } from "@/components/Countdown";
import { TikTokPanel } from "@/components/TikTokPanel";
import { useState } from "react";
import { useNow, useStore } from "@/lib/store";

type Kind = "posted" | "failed" | "queued" | "window";
type Ev = { id: string; at: number; title: string; meta: string; kind: Kind; clip?: string };
const KINDS: [Kind, string][] = [["posted", "Posted"], ["queued", "Posting"], ["failed", "Failed"], ["window", "Submit windows"]];

/** Schedule: what posted, what is posting, and the submit windows, a week at a time (today in the middle by default). */
export default function Schedule() {
  const { snap } = useStore();
  const now = useNow(30_000);
  const [week, setWeek] = useState(0);
  const [hide, setHide] = useState<Set<Kind>>(new Set());
  const title = (id: string) => snap.clips.find((c) => c.id === id)?.title ?? "Clip";
  const evs: Ev[] = [
    ...snap.publications.map((p): Ev => ({
      id: p.id, at: Date.parse(p.posted_at ?? p.created_at), title: title(p.clip_id), clip: p.clip_id,
      meta: `${p.label ?? p.platform ?? "post"} · ${p.status}`, kind: p.status === "posted" ? "posted" : p.status === "failed" ? "failed" : "queued",
    })),
    ...snap.submissions.map((s): Ev => ({ id: s.id, at: Date.parse(s.deadline_at), title: "Submit window closes", meta: s.submitted_at ? "submitted" : "Content Rewards", kind: "window" })),
  ];
  const start = new Date(now); start.setHours(0, 0, 0, 0);
  const days = Array.from({ length: 7 }, (_, i) => start.getTime() + (i - 3 + week * 7) * 86400_000);
  const inWeek = evs.filter((e) => e.at >= days[0] && e.at < days[6] + 86400_000);
  const shown = inWeek.filter((e) => !hide.has(e.kind));
  const posting = snap.publications.filter((p) => p.status === "pending" || p.status === "posting");
  const failed = snap.publications.filter((p) => p.status === "failed");
  const fmtD = (t: number) => new Date(t).toLocaleDateString([], { month: "short", day: "numeric" });
  return (
    <>
      <section className="hero" style={{ marginBottom: 28 }}>
        <div><h1>Schedule<br /><b>{posting.length} posting now.</b></h1>
          <p>Posts go out only after you approve (D020). YouTube and X post from the PC; TikTok is posted by hand.
            {failed.length > 0 && <> <Link href="/library" style={{ color: "var(--bad)", textDecoration: "underline" }}>{failed.length} failed post{failed.length === 1 ? "" : "s"}</Link>.</>}</p></div>
      </section>
      <div className="filters">
        <div className="seg" role="group" aria-label="Week">
          <button type="button" onClick={() => setWeek((w) => w - 1)} aria-label="Previous week">← Prev</button>
          <button type="button" className={week === 0 ? "on" : ""} onClick={() => setWeek(0)}>This week</button>
          <button type="button" onClick={() => setWeek((w) => w + 1)} aria-label="Next week">Next →</button>
        </div>
        <span className="mut" style={{ fontSize: 12 }}>{fmtD(days[0])} – {fmtD(days[6])}</span>
        <span style={{ flex: 1 }} />
        <div className="seg" role="group" aria-label="Show">
          {KINDS.map(([k, l]) => {
            const on = !hide.has(k);
            return <button key={k} type="button" className={on ? "on" : ""} aria-pressed={on}
              onClick={() => setHide((h) => { const n = new Set(h); if (on) n.add(k); else n.delete(k); return n; })}>
              <i className={`kdot ${k}`} />{l} <span style={{ opacity: 0.6 }}>{inWeek.filter((e) => e.kind === k).length}</span></button>;
          })}
        </div>
      </div>
      <div className="week">
        {days.map((d) => {
          const list = shown.filter((e) => e.at >= d && e.at < d + 86400_000).sort((a, b) => a.at - b.at);
          const date = new Date(d);
          return (
            <section key={d} className={`day${d === start.getTime() ? " today" : ""}`} aria-label={date.toDateString()}>
              <h4>{date.toLocaleDateString([], { weekday: "short" })}<span>{date.getDate()}</span></h4>
              {list.map((e) => {
                const body = <><b>{e.title}</b><span>{new Date(e.at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })} · {e.meta}</span></>;
                return e.clip
                  ? <Link key={e.id} href={`/library?clip=${encodeURIComponent(e.clip)}`} className={`ev ${e.kind} ev-link`} title="Open this clip in the Library">{body}</Link>
                  : <div key={e.id} className={`ev ${e.kind}`}>{body}</div>;
              })}
              {list.length === 0 && <span className="mut" style={{ fontSize: 11 }}>—</span>}
            </section>
          );
        })}
      </div>
      <div className="row2" style={{ marginTop: 40 }}>
        <ApprovedList />
        <Countdown />
      </div>
      <div style={{ marginTop: 18 }}><TikTokPanel /></div>
      <p className="quiet" style={{ marginTop: 18 }}>Want something changed before it posts? Open it from the <Link href="/" style={{ textDecoration: "underline" }}>review queue</Link> and press Edit clip.</p>
    </>
  );
}
