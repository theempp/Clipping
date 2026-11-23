"use client";
import Link from "next/link";
import { ago, compact } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { ownChannels, series } from "@/lib/view";
import { Spark } from "./Charts";
import { Icon } from "./Icon";

const META = {
  youtube: { name: "YouTube", icon: "yt", color: "var(--bad)", views: "views" },
  x: { name: "X", icon: "xlogo", color: "var(--tx)", views: "posts" },
  tiktok: { name: "TikTok", icon: "tt", color: "var(--c2)", views: "views" },
} as const;

/** Zo's own channels: live follower counts (YouTube, X via /api/live; TikTok typed in until the API audit). */
export function OwnChannels() {
  const { snap } = useStore();
  const now = useNow(10_000);
  const own = ownChannels(snap);
  return (
    <div className="row3">
      {(Object.keys(META) as (keyof typeof META)[]).map((k) => {
        const r = own[k], m = META[k];
        const hist = series(snap, `${k}:own`, "followers").map((p) => p.value);
        const prev = hist.length >= 2 ? hist[hist.length - 2] : null;
        const delta = r?.followers != null && prev != null ? r.followers - prev : null;
        const sec = k === "x" ? r?.posts : r?.views;
        return (
          <div key={k} className="glass stat">
            <div className="own">
              <span className="oi" style={{ color: m.color }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                {r?.avatar_url ? <img src={r.avatar_url} alt="" referrerPolicy="no-referrer" /> : <Icon name={m.icon} size={20} />}
              </span>
              <div style={{ minWidth: 0 }}>
                <b>{m.name}</b>
                <div className="mut" style={{ fontSize: 11 }}>
                  {r ? (k === "tiktok" ? `typed in ${ago(r.updated_at, now)}` : `updated ${ago(r.updated_at, now)}`) : k === "tiktok" ? "manual until API audit" : "key not set"}
                </div>
              </div>
            </div>
            <span className="sk"><Spark data={hist.slice(-10)} color={m.color} /></span>
            <div className="num sm tnum">{compact(r?.followers)}<small>followers</small></div>
            <div className="sub">
              {delta != null && <span style={{ color: delta >= 0 ? "var(--c2)" : "var(--bad)" }}>{delta >= 0 ? "↑" : "↓"} {compact(Math.abs(delta))} · </span>}
              {compact(sec)} {m.views}
              {k === "tiktok" && <> · <Link href="/settings#tiktok" style={{ textDecoration: "underline" }}>update</Link></>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
