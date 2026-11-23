"use client";
// Halo Pro review page sections (D116). Every widget reads real rows; missing data shows an empty state.
import Link from "next/link";
import { useMemo, useState, type CSSProperties } from "react";
import { rankQueue, pcState } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import type { Clip } from "@/lib/types";
import { BUDGET_USD, liveFor, streamerViews, type StreamerView } from "@/lib/view";
import {
  PLATFORM_LABEL, PLATFORMS, SPEND_LABEL, agoShort, channels7d, clipHeat, clipLen, clipScore, compactNum, isNew,
  judgeWhy, pipelineToday, queueSummary, spendView, streamerColor, subScores, upcomingPosts, type Platform,
} from "@/lib/halo";
import { HeadlineField, PostButton, PostChips, ReviewActions, sourceLine, useReview } from "./review";
import { Dial, Ico, PlatIco, QRing, sparkPath, useMedia } from "./ui";

const css = (v: Record<string, string | number>) => v as CSSProperties;

/** Queue in review order, with the hero (pinned or top pick) split off. */
export function useQueue() {
  const { snap } = useStore();
  const ui = useReview();
  const queue = useMemo(() => rankQueue(snap.clips), [snap.clips]);
  const pinned = ui.heroPin ? snap.clips.find((c) => c.id === ui.heroPin && (c.state === "pending_review" || c.state === "revise")) ?? null : null;
  const hero = pinned ?? queue[0] ?? null;
  return { queue, hero, rest: queue.filter((c) => c.id !== hero?.id) };
}

function nameOf(snap: ReturnType<typeof useStore>["snap"], c: Clip) {
  const s = snap.streamers.find((x) => x.id === c.streamer_id);
  return { name: s?.display_name ?? c.channel_key.split(":")[1] ?? "?", slug: s?.slug ?? c.channel_key.split(":")[1] ?? "", avatar: s?.avatar_url ?? null };
}

/* ---------------- streamer cards ---------------- */

function liveClock(since: string | null, now: number): string {
  if (!since) return "LIVE";
  const m = Math.max(0, Math.floor((now - Date.parse(since)) / 60_000));
  return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}`;
}

function StreamerCard({ v, i, clipsToday, bgPath }: { v: StreamerView; i: number; clipsToday: number; bgPath: string | null }) {
  const now = useNow(30_000);
  const bg = useMedia(bgPath);
  const color = streamerColor(v.s.slug);
  const plat = v.key?.startsWith("kick") ? "kick" : "twitch";
  const heat = v.heat.some((x) => x > 0) ? sparkPath(v.heat, 100, 28, 4) : "";
  const initials = v.s.display_name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  return (
    <Link href={`/streamers/${v.s.slug}`} className={`z-sc z-p${v.live ? "" : " z-off"}`} style={css({ "--i": i, "--c": color, "--img": bg ? `url("${bg}")` : "none" })}
      aria-label={`${v.s.display_name}: ${v.live ? `live${v.viewers != null ? `, ${v.viewers} watching` : ""}` : "offline"}`}>
      <span className={`z-bg${bg ? "" : " z-noimg"}`} />
      <span className="z-av">{v.s.avatar_url ? <img src={v.s.avatar_url} alt="" /> : <span>{initials}</span>}</span>
      <span className="z-nm">{v.s.display_name}{v.live && <PlatIco p={plat} size={13} />}</span>
      {v.live ? <span className="z-lv"><i />{liveClock(v.since, now)}</span> : <span className="z-lv z-off">OFF</span>}
      <span className="z-gm">{v.live ? [v.game, v.title].filter(Boolean).join(" · ") || "Live now" : "Offline"}</span>
      <span className="z-ft">
        <span className="z-vw"><b>{v.live && v.viewers != null ? compactNum(v.viewers) : "—"}</b><small>{v.live ? (v.since ? `live ${liveFor(v.since, now)}` : "watching") : "not live"}</small></span>
        <svg className="z-spk" viewBox="0 0 100 28" preserveAspectRatio="none" aria-label={heat ? "Chat heat, last hour" : "No chat heat yet"}>
          {heat ? <path d={heat} fill="none" style={{ stroke: "var(--spike)" }} strokeWidth="2" vectorEffect="non-scaling-stroke" />
            : <path d="M0 22 H100" style={{ stroke: "var(--dim)" }} strokeWidth="2" strokeDasharray="3 4" vectorEffect="non-scaling-stroke" />}
        </svg>
        <span className="z-cl">{clipsToday} clip{clipsToday === 1 ? "" : "s"}</span>
      </span>
    </Link>
  );
}

export function Pocket() {
  const { snap } = useStore();
  const now = useNow(15_000);
  const views = streamerViews(snap, now).filter((v) => v.inRoster || !snap.heartbeat?.status.roster).slice(0, 4);
  const start = new Date(now); start.setHours(0, 0, 0, 0);
  const st = pcState(snap.heartbeat, now);
  const capturing = st === "offline" ? [] : snap.heartbeat?.status.capturing ?? snap.heartbeat?.status.live ?? [];
  const latest = (id: string) => snap.clips.find((c) => c.streamer_id === id && c.thumb_path)?.thumb_path ?? null;
  const watched = snap.streamers.filter((s) => capturing.some((k) => k.endsWith(`:${s.twitch_login}`) || k.endsWith(`:${s.kick_slug}`)));
  return (
    <section className="z-pocket" aria-label="Streamers">
      {views.map((v, i) => (
        <StreamerCard key={v.s.id} v={v} i={i} bgPath={latest(v.s.id)}
          clipsToday={snap.clips.filter((c) => c.streamer_id === v.s.id && Date.parse(c.created_at) >= start.getTime()).length} />
      ))}
      {views.length === 0 && <div className="z-p z-empty" style={{ gridRow: "1 / 5" }}><div><b>No streamers yet</b>The worker adds them from its channel config.</div></div>}
      {Array.from({ length: views.length ? 4 - views.length : 0 }, (_, i) => <span key={`pad${i}`} aria-hidden="true" />)}
      <div className={`z-agent${st === "offline" ? " z-down" : ""}`}>
        <span className="z-stackav">
          {watched.slice(0, 3).map((s) => (s.avatar_url ? <img key={s.id} src={s.avatar_url} alt="" /> : <span key={s.id}>{s.display_name[0]}</span>))}
          {watched.length === 0 && <span>·</span>}
        </span>
        <div><b>{st === "offline" ? "PC not reporting" : `${capturing.length} agent${capturing.length === 1 ? "" : "s"} watching`}</b>
          <small>{st === "offline" ? (snap.heartbeat ? `last seen ${agoShort(snap.heartbeat.seen_at, now)}` : "no heartbeat yet") : capturing.length ? "clipping in real time" : "no one live right now"}</small></div>
        <span className="z-ok">{st === "offline" ? "OFF" : "ON"}</span>
      </div>
    </section>
  );
}

/* ---------------- hero ---------------- */

export function Hero({ clip, rank }: { clip: Clip | null; rank: number }) {
  const { snap, pending } = useStore();
  const ui = useReview();
  const now = useNow(30_000);
  const src = useMedia(clip?.storage_path);
  const poster = useMedia(clip?.thumb_path);
  if (!clip) {
    return (
      <section className="z-hero z-p" style={css({ "--i": 1 })} aria-label="Clip waiting for approval">
        <div className="z-empty" style={{ gridColumn: "1 / -1" }}><div><b>Queue clear</b>New clips land here the moment the PC finishes render and QA. Nothing posts without you.</div></div>
      </section>
    );
  }
  const who = nameOf(snap, clip);
  const s = subScores(clip);
  const why = judgeWhy(clip);
  const heat = clipHeat(snap.candidates, clip);
  const on = ui.staged.has(clip.id);
  const waiting = pending?.clip.id === clip.id;
  const fixing = clip.state === "revise";
  const hookWin = typeof clip.judge?.hook_window === "string" ? clip.judge.hook_window : null;
  const qa = clip.qa as Record<string, unknown>;
  const capPx = typeof clip.manifest?.caption_px === "number" ? clip.manifest.caption_px : typeof qa?.caption_px === "number" ? qa.caption_px : null;
  const flashes = typeof qa?.flashes_per_s === "number" ? qa.flashes_per_s : null;
  const facts: [string, string][] = [["Hook lands", hookWin ?? "—"], ["Captions", capPx != null ? `${capPx} px` : "—"], ["Flashes", flashes != null ? `${flashes} / s` : "—"], ["Length", clipLen(clip.duration_s)]];
  const badges = Array.isArray(clip.judge?.badges) ? (clip.judge.badges as unknown[]).filter((b): b is string => typeof b === "string") : [];
  return (
    <section className={`z-hero z-p${on ? " z-approved" : ""}`} style={css({ "--i": 1 })} aria-label="Clip waiting for approval">
      <div className="z-bgv" aria-hidden="true" style={css({ "--bgimg": poster ? `url("${poster}")` : "none" })} />
      <div className="z-vidcol">
        <div className="z-p9">
          {src ? <video key={src} src={src} poster={poster ?? undefined} autoPlay muted loop playsInline /> : <span className="z-ph9">Loading clip…</span>}
          <span className="z-tp">{rank === 0 && <span className="z-rk">#1 PICK</span>}{badges.includes("clip_that") ? <span>CLIP THAT</span> : clip.channel_key.includes(":") && <span>LIVE CLIP</span>}</span>
        </div>
        {heat ? (
          <>
            <div className="z-heat" aria-label={`Chat heat across the clip, ${heat.ratio}x spike`}>
              {heat.h.map((h, i) => <i key={i} className={heat.spike[i] ? "z-s" : ""} style={{ height: `${Math.max(8, h * 100)}%` }} />)}
            </div>
            <div className="z-heatl"><span>chat heat</span><span>{heat.ratio}x spike</span></div>
          </>
        ) : <><div className="z-heat z-none">no chat readings for this moment</div><div className="z-heatl"><span>chat heat</span><span>—</span></div></>}
      </div>
      <div className="z-hinfo">
        <span className="z-lbl">{sourceLine(clip, who.name, now)}</span>
        <h1>{clip.title ?? clip.job_id}</h1>
        <div className="z-hst">
          {ui.edited.has(clip.id) && <span className="z-tag z-ed">Edited by you · saved</span>}
          {fixing ? <span className="z-tag z-run">Re-rendering on the PC</span>
            : waiting ? <span className="z-tag z-wait">Posting · undo below</span>
            : on ? <span className="z-tag z-ok">Approved · ready to post</span>
            : <span className="z-tag">Waiting for you</span>}
          {clip.revise_failed && <span className="z-tag z-bad">Last revision failed QA</span>}
        </div>
        <div className="z-sco"><Dial score={clipScore(clip)} size={78} />
          <div className="z-brk">
            {([["Hook", s.hook], ["Payoff", s.payoff], ["Trend", s.trend]] as const).map(([k, v]) => (
              <span key={k}><b className={v == null ? "z-na" : ""}>{v ?? "—"}</b>{k}<i><i style={{ width: `${v ?? 0}%` }} /></i></span>
            ))}
            <span className="z-evv"><b>{compactNum(s.views)}</b>Est. views</span>
          </div>
        </div>
        {why && <p className="z-why"><b>GROK</b><span>{why}</span></p>}
        <div className="z-facts">{facts.map(([k, v]) => <div key={k}><small>{k}</small><b>{v}</b></div>)}</div>
        <HeadlineField clip={clip} id="h-in" />
        <ReviewActions clip={clip} />
        <div className="z-postrow"><span className="z-lbl">Post to</span><PostChips clip={clip} /><span className="z-sp" /><PostButton clip={clip} /></div>
      </div>
    </section>
  );
}

/* ---------------- queue ---------------- */

function QueueRow({ c, i }: { c: Clip; i: number }) {
  const { snap } = useStore();
  const ui = useReview();
  const now = useNow(30_000);
  const thumb = useMedia(c.thumb_path);
  const [hover, setHover] = useState(false);
  const vid = useMedia(hover ? c.storage_path : null);
  const who = nameOf(snap, c);
  const s = subScores(c);
  const on = ui.staged.has(c.id);
  return (
    <li>
      <button type="button" className={`z-qi${on ? " z-done" : ""}`} style={css({ "--d": `${i * 45}ms`, "--c": streamerColor(who.slug) })}
        onClick={() => ui.openPop(c.id)} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)} aria-label={`Open ${c.title ?? c.job_id}`}>
        <span className="z-qth">{thumb ? <img src={thumb} alt="" /> : <span className="z-ph9" />}
          {hover && vid && <video src={vid} muted autoPlay loop playsInline />}<em>{clipLen(c.duration_s)}</em></span>
        <span className="z-qtx">
          <span className="z-qtop">{isNew(c, now) && <span className="z-new">NEW</span>}
            <span className="z-qwho">{who.avatar ? <img className="z-qav" src={who.avatar} alt="" /> : <span className="z-qav z-txt">{who.name[0]}</span>}{who.name}</span>
            <span>{agoShort(c.created_at, now)}</span></span>
          <b>{c.title ?? c.job_id}</b>
          <span className="z-qmeta">{on ? <span className="z-tag z-ok">Approved</span> : <><span>Hook {s.hook ?? "—"}</span>{s.views != null && <span>Est. {compactNum(s.views)}</span>}{c.revision > 0 && <span>rev {c.revision}</span>}</>}</span>
        </span>
        <QRing score={clipScore(c)} />
      </button>
    </li>
  );
}

export function Queue({ queue, rest }: { queue: Clip[]; rest: Clip[] }) {
  const { snap } = useStore();
  const now = useNow(30_000);
  const [who, setWho] = useState<string | null>(null);
  const sum = queueSummary(queue, now);
  const names = snap.streamers.filter((s) => queue.some((c) => c.streamer_id === s.id));
  const list = who ? rest.filter((c) => c.streamer_id === who) : rest;
  return (
    <section className="z-queue z-p" id="queue" style={css({ "--i": 2 })} aria-label="Queue">
      <div className="z-qh"><h2>Queue</h2><span className="z-n">{queue.length}</span><span className="z-sp" /><span className="z-lbl">Best first</span></div>
      <div className="z-qsum"><div><b>{sum.waiting}</b><small>waiting</small></div><div><b>{sum.avg ?? "—"}</b><small>avg score</small></div><div><b>{sum.fresh}</b><small>new · 15 min</small></div></div>
      {names.length > 1 && (
        <div className="z-qf" role="group" aria-label="Filter by streamer">
          <button type="button" className={who === null ? "z-on" : ""} onClick={() => setWho(null)}>All</button>
          {names.slice(0, 4).map((s) => (
            <button key={s.id} type="button" className={who === s.id ? "z-on" : ""} style={css({ "--c": streamerColor(s.slug) })} onClick={() => setWho(s.id)}>
              <i />{s.display_name.split(" ")[0]}</button>
          ))}
        </div>
      )}
      <ul className="z-id-queue">
        {list.map((c, i) => <QueueRow key={c.id} c={c} i={i} />)}
        {list.length === 0 && <li className="z-empty"><div><b>{queue.length ? "Nothing else waiting" : "Queue clear"}</b>{queue.length ? "The top pick is on the left." : "New clips land here after render and QA."}</div></li>}
      </ul>
    </section>
  );
}

/* ---------------- bottom widgets ---------------- */

export function Spend() {
  const { snap } = useStore();
  const now = useNow(60_000);
  const sv = spendView(snap, snap.spendDays, now);
  const colors = ["var(--halo)", "var(--vio)", "var(--ok)", "var(--warn)", "var(--tt)"];
  const month = new Date(now).toLocaleString("en-US", { month: "short" });
  const line = sv.series ? sparkPath(sv.series, 200, 40, 4) : "";
  return (
    <section className="z-spend z-w z-p" style={css({ "--i": 3 })} aria-label="AI spend">
      <div className="z-wh"><span className="z-lbl"><Ico n="coin" />AI spend · {month}</span></div>
      <div className="z-big">${sv.total.toFixed(2)} <small>/ ${BUDGET_USD}</small></div>
      <div className="z-bud" aria-label={`Spend by kind${sv.pace != null ? `, month pace $${sv.pace.toFixed(2)}` : ""}`}>
        {sv.kinds.map((k, i) => <i key={k.kind} style={{ width: `${Math.min(100, (k.usd / BUDGET_USD) * 100)}%`, background: colors[i % colors.length] }} />)}
        {sv.pace != null && <span className="z-pj" style={{ left: `${Math.min(99, (sv.pace / BUDGET_USD) * 100)}%` }} />}
      </div>
      <div className="z-leg">
        {sv.kinds.length ? sv.kinds.slice(0, 4).map((k, i) => <span key={k.kind} style={css({ "--c": colors[i % colors.length] })}>{SPEND_LABEL[k.kind] ?? k.kind} <b>${k.usd.toFixed(2)}</b></span>)
          : <span style={css({ "--c": "var(--dim)" })}>No spend logged this month</span>}
      </div>
      {line ? (
        <svg className="z-spark" viewBox="0 0 200 40" preserveAspectRatio="none" aria-label="Daily spend, last 14 days">
          <path d={`${line} L200 40 L0 40Z`} fill="url(#sg)" /><path d={line} fill="none" style={{ stroke: "var(--halo)" }} strokeWidth="2" vectorEffect="non-scaling-stroke" />
        </svg>
      ) : <div className="z-empty" style={{ padding: 4 }}>Daily spend shows here once the PC logs some.</div>}
      <div className="z-sr"><span>Today <b>{sv.today != null ? `$${sv.today.toFixed(2)}` : "—"}</b></span>
        <span>Month pace <b style={{ color: sv.pace != null && sv.pace > BUDGET_USD ? "var(--bad)" : "var(--warn)" }}>{sv.pace != null ? `$${sv.pace.toFixed(2)}` : "—"}</b></span></div>
    </section>
  );
}

export function Funnel() {
  const { snap } = useStore();
  const now = useNow(30_000);
  const f = pipelineToday(snap, now);
  const steps: [string, number][] = [["Found", f.found], ["Judged", f.judged], ["Passed", f.passed], ["Okayed", f.okayed], ["Posted", f.posted]];
  const max = Math.max(1, ...steps.map(([, n]) => n));
  return (
    <section className="z-w z-p" style={css({ "--i": 4 })} aria-label="Today's pipeline">
      <div className="z-wh"><span className="z-lbl"><Ico n="funnel" />Today&apos;s pipeline</span></div>
      <div className="z-fun">
        {steps.map(([k, n]) => (
          <div key={k} className="z-fs"><b className={n ? "" : "z-zero"}>{n}</b><span className="z-bar" style={{ height: `${Math.max(4, (n / max) * 100)}%` }} /><small>{k}</small></div>
        ))}
      </div>
    </section>
  );
}

export function Next24() {
  const { snap } = useStore();
  const ui = useReview();
  const now = useNow(60_000);
  const up = upcomingPosts(snap.clips, snap.publications);
  const rows: [Platform, string, string][] = [["youtube", "z-yt", "16%"], ["tiktok", "z-tt", "48%"], ["x", "z-x", "80%"]];
  const hrs = [0, 6, 12, 18, 24].map((h) => new Date(now + h * 3600_000).toLocaleTimeString("en-US", { hour: "numeric" }));
  const ev = up.flatMap((c, i) => (c.post_platforms?.length ? c.post_platforms : ui.postable).map((p) => ({ c, p: p as Platform, i })));
  return (
    <section className="z-w z-p" style={css({ "--i": 5 })} aria-label="Posting schedule, next 24 hours">
      <div className="z-wh"><span className="z-lbl"><Ico n="clock" />Next 24 h</span><span className="z-sp" />
        <span className="z-delta" style={{ color: "var(--halo)", background: "rgba(143,196,255,.12)" }}>{up.length} queued</span></div>
      <div className="z-lane24">
        {rows.map(([p, cls, top]) => (
          <span key={p}>
            <div className="z-row" style={{ top }} />
            <span className={`z-rl ${cls}`} style={{ top }} title={PLATFORM_LABEL[p]}><PlatIco p={p} size={13} /></span>
          </span>
        ))}
        {ev.map(({ c, p, i }) => <LaneEvent key={`${c.id}${p}`} clip={c} top={rows.find((r) => r[0] === p)?.[2] ?? "48%"} x={0.08 + i * 0.17} first={i === 0} />)}
        <span className="z-now" style={{ left: "calc(30px + (100% - 30px) * .03)" }} />
        {up.length === 0 && <span className="z-emptyl">Nothing queued. Approved clips post right after you confirm; the D088 ramp spaces them out.</span>}
        <div className="z-hrs">{hrs.map((h, i) => <span key={i}>{i === 0 ? "now" : h}</span>)}</div>
      </div>
    </section>
  );
}

function LaneEvent({ clip, top, x, first }: { clip: Clip; top: string; x: number; first: boolean }) {
  const thumb = useMedia(clip.thumb_path);
  return (
    <span className={`z-ev${first ? " z-s" : ""}`} style={{ left: `calc(30px + (100% - 30px) * ${Math.min(0.95, x)})`, top }} title={clip.title ?? clip.job_id}>
      <span style={{ backgroundImage: thumb ? `url("${thumb}")` : undefined }} /><em>{clip.state === "scheduled" ? "posting" : "in line"}</em>
    </span>
  );
}

export function Channels() {
  const { snap } = useStore();
  const now = useNow(60_000);
  const ch = channels7d(snap, now);
  const ic: Record<Platform, CSSProperties> = {
    youtube: { background: "rgba(255,59,59,.16)", color: "var(--yt)" }, tiktok: { background: "rgba(37,244,238,.12)", color: "var(--tt)" },
    x: { background: "rgba(255,255,255,.1)", color: "var(--tx)" },
  };
  return (
    <section className="z-w z-p" style={css({ "--i": 6 })} aria-label="Channel growth this week">
      <div className="z-wh"><span className="z-lbl"><Ico n="trend" />Channels · 7 days</span></div>
      <div className="z-chg">
        {PLATFORMS.map((p) => {
          const r = ch[p];
          const shown = r.gained ?? r.views;
          return (
            <div key={p} className="z-ch">
              <span className="z-ic" style={ic[p]}><PlatIco p={p} size={14} /></span>
              <span><b className={shown == null ? "z-na" : ""}>{compactNum(shown)}</b><small>{r.gained != null ? "views" : r.views != null ? "total" : p === "tiktok" ? "by hand" : "no data yet"}</small></span>
              <span className={`z-delta${r.growth == null ? " z-na" : r.growth < 0 ? " z-dn" : ""}`}>{r.growth == null ? "—" : `${r.growth >= 0 ? "+" : ""}${r.growth}%`}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

