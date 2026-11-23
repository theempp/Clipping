"use client";
import Link from "next/link";
import { ApprovedList } from "@/components/ApprovedList";
import { Countdown } from "@/components/Countdown";
import { TikTokPanel } from "@/components/TikTokPanel";
import { useNow, useStore } from "@/lib/store";

type Ev = { id: string; at: number; title: string; meta: string; kind: "posted" | "failed" | "queued" | "window" };

/** Schedule: what posted, what is posting, and the submit windows, laid out over the past three days and next three. */
export default function Schedule() {
  const { snap } = useStore();
  const now = useNow(30_000);
  const title = (id: string) => snap.clips.find((c) => c.id === id)?.title ?? "Clip";
  const evs: Ev[] = [
    ...snap.publications.map((p): Ev => ({
      id: p.id, at: Date.parse(p.posted_at ?? p.created_at), title: title(p.clip_id),
      meta: `${p.label ?? p.platform ?? "post"} · ${p.status}`, kind: p.status === "posted" ? "posted" : p.status === "failed" ? "failed" : "queued",
    })),
    ...snap.submissions.map((s): Ev => ({ id: s.id, at: Date.parse(s.deadline_at), title: "Submit window closes", meta: s.submitted_at ? "submitted" : "Content Rewards", kind: "window" })),
  ];
  const start = new Date(now); start.setHours(0, 0, 0, 0);
  const days = Array.from({ length: 7 }, (_, i) => start.getTime() + (i - 3) * 86400_000);
  const posting = snap.publications.filter((p) => p.status === "pending" || p.status === "posting");
  return (
    <>
      <section className="hero" style={{ marginBottom: 28 }}>
        <div><h1>Schedule<br /><b>{posting.length} posting now.</b></h1>
          <p>Posts go out only after you approve (D020). YouTube and X post from the PC; TikTok is posted by hand.</p></div>
      </section>
      <div className="week">
        {days.map((d) => {
          const list = evs.filter((e) => e.at >= d && e.at < d + 86400_000).sort((a, b) => a.at - b.at);
          const date = new Date(d);
          return (
            <section key={d} className={`day${d === start.getTime() ? " today" : ""}`} aria-label={date.toDateString()}>
              <h4>{date.toLocaleDateString([], { weekday: "short" })}<span>{date.getDate()}</span></h4>
              {list.map((e) => (
                <div key={e.id} className={`ev ${e.kind}`}>
                  <b>{e.title}</b>
                  <span>{new Date(e.at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })} · {e.meta}</span>
                </div>
              ))}
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
