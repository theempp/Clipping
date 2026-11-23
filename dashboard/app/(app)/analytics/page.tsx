"use client";
import { useMemo, useState } from "react";
import { Bars, LineChart, Ring } from "@/components/Charts";
import { OwnChannels } from "@/components/OwnChannels";
import { AgentTicker } from "@/components/Pipeline";
import { WeekPulse } from "@/components/WeekPulse";
import { compact } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { BUDGET_USD, monthSpend, series, streamerViews } from "@/lib/view";

type Tab = "growth" | "money" | "pipeline";
type Range = 7 | 30;

/** Analytics: Growth (Zo's channels), Money (spend vs budget, submit windows), Pipeline (funnel + agents). */
export default function Analytics() {
  const [tab, setTab] = useState<Tab>("growth");
  return (
    <>
      <section className="hero"><h1>Analytics</h1></section>
      <div style={{ height: 22 }} />
      <div className="bigtabs" role="tablist" aria-label="Analytics">
        {(["growth", "money", "pipeline"] as Tab[]).map((t) => (
          <button key={t} type="button" role="tab" aria-selected={tab === t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      {tab === "growth" && <Growth />}
      {tab === "money" && <Money />}
      {tab === "pipeline" && <Pipeline />}
    </>
  );
}

/** One value per day for the last `days` days (last known value carried forward). */
function daily(points: { at: string; value: number }[], days: number, now: number): (number | null)[] {
  const out: (number | null)[] = [];
  let i = 0, last: number | null = null;
  const sorted = [...points].sort((a, b) => a.at.localeCompare(b.at));
  for (let d = days - 1; d >= 0; d--) {
    const end = now - d * 86400_000;
    while (i < sorted.length && Date.parse(sorted[i].at) <= end) last = sorted[i++].value;
    out.push(last);
  }
  return out;
}

function Growth() {
  const { snap } = useStore();
  const now = useNow(60_000);
  const [range, setRange] = useState<Range>(30);
  const yt = daily(series(snap, "youtube:own", "views"), range, now);
  const tt = daily(series(snap, "tiktok:own", "views"), range, now);
  const total = yt.map((v, i) => (v ?? 0) + (tt[i] ?? 0));
  const has = total.some((v) => v > 0);
  const labels = Array.from({ length: range }, (_, i) => {
    const d = new Date(now - (range - 1 - i) * 86400_000);
    return range === 7 ? d.toLocaleDateString([], { weekday: "short" }) : i % 6 === 0 ? `${d.getMonth() + 1}/${d.getDate()}` : "";
  });
  const views = streamerViews(snap, now);
  const per = views.slice(0, 6).map((v) => ({
    v, posted: snap.clips.filter((c) => c.streamer_id === v.s.id && c.state === "published").length,
    made: snap.clips.filter((c) => c.streamer_id === v.s.id).length,
  }));
  const results = [...snap.results].sort((a, b) => (b.follows_per_1k ?? -1) - (a.follows_per_1k ?? -1));
  return (
    <>
      <div className="glass">
        <div className="hd">
          <div><span className="mut" style={{ fontSize: 12 }}>Total views · YouTube + TikTok · {range} d</span>
            <div className="num" style={{ margin: "4px 0 0" }}>{has ? compact(total[total.length - 1]) : "—"}</div></div>
          <div className="seg" role="tablist" aria-label="Range">
            <button type="button" className={range === 7 ? "on" : ""} onClick={() => setRange(7)}>7D</button>
            <button type="button" className={range === 30 ? "on" : ""} onClick={() => setRange(30)}>1M</button>
          </div>
        </div>
        <LineChart height={260} labels={labels} fmt={(x) => compact(x)} empty="Views appear once YouTube or TikTok numbers come in"
          series={has ? [{ name: "YouTube", color: "var(--acc)", values: yt.map((v) => v ?? 0) }, { name: "TikTok", color: "var(--c3)", values: tt.map((v) => v ?? 0) }] : []} />
        <div className="legend"><span><i style={{ background: "var(--acc)" }} />YouTube</span><span><i style={{ background: "var(--c3)" }} />TikTok</span></div>
      </div>
      <div className="sec"><h2>Your channels</h2><span>followers, live</span></div>
      <OwnChannels />
      <div className="sec"><h2>By streamer</h2><span>clips made · posted</span></div>
      <div className="row3">
        {per.map(({ v, posted, made }) => (
          <div key={v.s.id} className="glass stat">
            <span className="lab full">{v.s.display_name}</span>
            <div className="num sm">{posted}<small>posted of {made}</small></div>
          </div>
        ))}
      </div>
      {results.length > 0 && <>
        <div className="sec"><h2>TikTok long-form tests</h2><span>best follows per 1K first</span></div>
        <div className="glass scroll-x">
          <table className="tbl">
            <thead><tr><th>Cell</th><th>Posts</th><th>Notices</th><th>Avg watch</th><th>5 s hold</th><th>Follows/1K</th><th>RPM</th></tr></thead>
            <tbody>{results.map((r) => (
              <tr key={`${r.format}${r.pacing}${r.caption_style}${r.voice}${r.layout}`}>
                <td>{r.format} · {r.pacing} · {r.caption_style} · {r.voice} · {r.layout}</td><td>{r.posts}</td>
                <td className={r.notices >= 2 ? "bad" : ""}>{r.notices}</td><td>{r.avg_watch_s != null ? `${r.avg_watch_s}s` : "—"}</td>
                <td>{r.hold_5s_pct != null ? `${r.hold_5s_pct}%` : "—"}</td><td>{r.follows_per_1k ?? "—"}</td><td>{r.rpm_usd != null ? `$${r.rpm_usd}` : "—"}</td>
              </tr>))}</tbody>
          </table>
        </div>
      </>}
    </>
  );
}

const KIND: Record<string, string> = { grok: "Grok", x_post: "X API", storage: "Storage", youtube: "YouTube", transcribe: "Transcribe" };

function Money() {
  const { snap } = useStore();
  const now = useNow(60_000);
  const spend = monthSpend(snap);
  const pct = Math.round((spend.total / BUDGET_USD) * 100);
  const kinds = useMemo(() => {
    const m = new Map<string, number>();
    for (const s of snap.spend) m.set(s.kind, (m.get(s.kind) ?? 0) + s.usd);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [snap.spend]);
  const subs = snap.submissions;
  const done = subs.filter((s) => s.submitted_at).length;
  const missed = subs.filter((s) => !s.submitted_at && Date.parse(s.deadline_at) < now).length;
  const active = snap.campaigns.filter((c) => c.status === "active");
  return (
    <>
      <div className="row2">
        <div className="glass">
          <div className="hd"><h3>Spent this month by kind</h3><span className="r">USD</span></div>
          {kinds.length ? <Bars data={kinds.map(([k, v], i) => ({ label: KIND[k] ?? k, value: Math.round(v), color: ["var(--acc)", "var(--c3)", "var(--c2)", "var(--warn)"][i % 4] }))} height={230} />
            : <p className="quiet">No spend logged this month.</p>}
        </div>
        <div className="glass" style={{ textAlign: "center" }}>
          <div className="hd"><h3>Budget</h3><span className="r">${BUDGET_USD} / month ceiling (D012)</span></div>
          <Ring pct={pct} size={180} w={14} color={pct > 90 ? "var(--bad)" : "var(--acc)"} label={`${pct}% of budget used`} />
          <p className="mut" style={{ fontSize: 12 }}>${spend.total.toFixed(0)} spent · {kinds.map(([k, v]) => `${KIND[k] ?? k} $${v.toFixed(0)}`).join(" · ") || "nothing yet"}</p>
        </div>
      </div>
      <div className="row3" style={{ marginTop: 18 }}>
        <div className="glass stat"><span className="lab full">Submit windows · 24h</span><div className="num sm">{done}<small>submitted</small></div><div className="sub">{missed} missed · {subs.length - done - missed} open</div></div>
        <div className="glass stat"><span className="lab full">Active campaigns</span><div className="num sm">{active.length}</div>
          <div className="sub">{active.length ? `best CPM $${Math.max(...active.map((c) => c.cpm_usd ?? 0)).toFixed(2)}` : "none running"}</div></div>
        <div className="glass stat"><span className="lab full">Earned</span><div className="num sm">—</div><div className="sub">Payouts are not tracked yet. TikTok rewards come from the manual stats.</div></div>
      </div>
    </>
  );
}

function Pipeline() {
  const { snap } = useStore();
  const cands = snap.candidates;
  const kept = cands.filter((c) => c.outcome === "kept").length;
  const recent = snap.clips;
  const steps = [
    { n: cands.length, l: "Moments scored · 6h", a: 0.5 },
    { n: kept, l: "Kept by detector", a: 0.38 },
    { n: recent.length, l: "Rendered clips", a: 0.28 },
    { n: recent.filter((c) => ["approved", "scheduled", "published"].includes(c.state)).length, l: "Approved", a: 0.18 },
    { n: recent.filter((c) => c.state === "published").length, l: "Posted", a: 0.1 },
  ];
  return (
    <>
      <div className="steps">{steps.map((s) => <div key={s.l} style={{ "--a": s.a } as React.CSSProperties}><b>{compact(s.n)}</b><span>{s.l}</span></div>)}</div>
      <div className="sec"><h2>Agent health</h2><span>this hour</span></div>
      <AgentTicker />
      <div style={{ marginTop: 18 }}><WeekPulse /></div>
    </>
  );
}
