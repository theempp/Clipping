"use client";
import { useEffect, useState } from "react";
import { Avatar } from "@/components/Avatar";
import { BrainWeights } from "@/components/Brain";
import { LearnedRules } from "@/components/LearnedRules";
import { WakeToggle } from "@/components/WakeToggle";
import { PC_NAME } from "@/lib/env";
import { ago, pcState } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { BUDGET_USD, monthSpend, ownChannels, streamerViews } from "@/lib/view";

type Sources = { twitch: boolean; kick: boolean; youtube: boolean; x: boolean; tiktok: "manual" };

export default function Settings() {
  const { snap, demo, pollLive, signOut } = useStore();
  const now = useNow(5000);
  const views = streamerViews(snap, now);
  const [pick, setPick] = useState<string | null>(null);
  const cur = views.find((v) => v.s.id === pick) ?? views[0];
  const [src, setSrc] = useState<Sources | null>(null);
  const [writer, setWriter] = useState<boolean | null>(null);
  useEffect(() => {
    void fetch("/api/live").then((r) => r.json()).then((j: { configured?: Sources; writer?: boolean }) => {
      if (j.configured) setSrc(j.configured);
      setWriter(j.writer ?? null);
    }).catch(() => {});
  }, []);
  const st = pcState(snap.heartbeat, snap.control.awake, now);
  const gpu = snap.heartbeat?.status.gpu;
  const spend = monthSpend(snap);
  const lastLive = snap.live.reduce((m, r) => Math.max(m, Date.parse(r.updated_at)), 0);

  return (
    <>
      <section className="hero" style={{ marginBottom: 28 }}><h1>Settings</h1></section>
      <div className="row2e">
        <div className="stack">
          <section className="glass" aria-label="Machine">
            <div className="hd"><h3>{PC_NAME}</h3><span className="r">{st}</span></div>
            <WakeToggle />
            <div className="set-row"><div className="tx"><b>GPU</b><span>{gpu?.name ?? "unknown"}{gpu?.mem_used_gb != null ? ` · ${gpu.mem_used_gb}/${gpu.mem_total_gb} GB` : ""}</span></div><b className="tnum">{st === "offline" ? "—" : `${gpu?.util ?? 0}%`}</b></div>
            <div className="set-row"><div className="tx"><b>Last heartbeat</b><span>worker {snap.heartbeat?.worker_id ?? "—"} · v{snap.heartbeat?.status.version ?? "?"}</span></div><span className="mut">{snap.heartbeat ? ago(snap.heartbeat.seen_at, now) : "never"}</span></div>
            <div className="set-row"><div className="tx"><b>Spend this month</b><span>budget ceiling ${BUDGET_USD} (D012)</span></div><b className="tnum">${spend.total.toFixed(0)}</b></div>
          </section>

          <section className="glass" aria-label="Live numbers">
            <div className="hd"><h3>Live numbers</h3><button type="button" className="b" onClick={() => void pollLive(true)}>Refresh now</button></div>
            <p className="quiet">The server polls each platform about once a minute while the dashboard is open, and Supabase Realtime pushes every change here. Keys live only in the server env, never in the browser.</p>
            {([["twitch", "Twitch Helix", "TWITCH_CLIENT_ID + TWITCH_CLIENT_SECRET"], ["kick", "Kick", "KICK_CLIENT_ID + KICK_CLIENT_SECRET"],
              ["youtube", "YouTube", "YOUTUBE_API_KEY + YOUTUBE_CHANNEL_ID"], ["x", "X", "X_BEARER_TOKEN + X_USERNAME"]] as const).map(([k, name, env]) => (
              <div key={k} className="set-row">
                <div className="tx"><b>{name}</b><span>{env}</span></div>
                <span className={`pill ${src == null ? "" : src[k] ? "ok" : "warn"}`}>{src == null ? "checking" : src[k] ? "connected" : "key not set"}</span>
              </div>
            ))}
            <div className="set-row"><div className="tx"><b>TikTok</b><span>manual until the API audit (D074)</span></div><span className="pill">manual</span></div>
            <div className="set-row"><div className="tx"><b>Server writer</b><span>SUPABASE_SERVICE_ROLE_KEY on the host</span></div>
              <span className={`pill ${writer ? "ok" : demo ? "" : "warn"}`}>{demo ? "demo" : writer ? "set" : "not set"}</span></div>
            <p className="quiet">Last update {lastLive ? ago(new Date(lastLive).toISOString(), now) : "never"}.</p>
          </section>

          <TikTokChannel />
        </div>

        <div className="stack">
          <section className="glass" id="brain" aria-label="Streamer brain">
            <div className="hd"><h3>Streamer brain</h3><span className="r">what the detector weighs</span></div>
            <div className="chips" style={{ marginBottom: 14 }}>
              {views.map((v) => (
                <button key={v.s.id} type="button" className={`chip${cur?.s.id === v.s.id ? " on" : ""}`} onClick={() => setPick(v.s.id)}>
                  <Avatar s={v.s} size={18} /> {v.s.display_name}
                </button>
              ))}
            </div>
            {cur && <BrainWeights s={cur.s} edit />}
          </section>
          <section className="glass" aria-label="Learned rules">
            <div className="hd" style={{ marginBottom: 0 }}><h3>Revision rules</h3><span className="r">from your notes (D078)</span></div>
            <LearnedRules />
            {!snap.rules.length && <p className="quiet">None yet. Revise a clip with “fix this on every clip” on and it shows up here.</p>}
          </section>
          {!demo && (
            <section className="glass"><div className="set-row"><div className="tx"><b>Sign out</b><span>Owner-only magic link (D054)</span></div>
              <button type="button" className="b" onClick={() => void signOut()}>Sign out</button></div></section>
          )}
        </div>
      </div>
    </>
  );
}

function TikTokChannel() {
  const { snap, setTiktokChannel } = useStore();
  const now = useNow(30_000);
  const t = ownChannels(snap).tiktok;
  const [f, setF] = useState({ followers: "", views: "", posts: "" });
  const [saved, setSaved] = useState(false);
  const n = (s: string) => (s.trim() === "" ? null : Math.max(0, Math.round(Number(s))));
  const ok = Object.values(f).some((v) => v.trim() !== "" && Number.isFinite(Number(v)));
  return (
    <section className="glass" id="tiktok" aria-label="TikTok channel numbers">
      <div className="hd"><h3>TikTok channel</h3><span className="r">{t ? `last typed ${ago(t.updated_at, now)}` : "not entered yet"}</span></div>
      <div className="tt-form">
        {(["followers", "views", "posts"] as const).map((k) => (
          <label key={k}><span>{k[0].toUpperCase() + k.slice(1)}{t?.[k] != null ? ` (now ${t[k]!.toLocaleString()})` : ""}</span>
            <input className="in" type="number" min={0} inputMode="numeric" value={f[k]} onChange={(e) => { setF((x) => ({ ...x, [k]: e.target.value })); setSaved(false); }} />
          </label>
        ))}
        <button type="button" className="b ok" disabled={!ok}
          onClick={async () => { if (await setTiktokChannel(n(f.followers) ?? t?.followers ?? null, n(f.views) ?? t?.views ?? null, n(f.posts) ?? t?.posts ?? null)) { setSaved(true); setF({ followers: "", views: "", posts: "" }); } }}>
          {saved ? "Saved" : "Save"}
        </button>
      </div>
      <p className="quiet">Per-video TikTok stats are entered on each long video in Review.</p>
    </section>
  );
}
