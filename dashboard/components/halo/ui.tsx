"use client";
// Halo Pro building blocks (D116): icons, score dial, queue ring, platform marks, signed media.
import { useEffect, useState } from "react";
import type { Platform } from "@/lib/halo";
import { useStore } from "@/lib/store";

const P: Record<string, string> = {
  live: "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6ZM6.3 6.3a8 8 0 0 0 0 11.4M17.7 6.3a8 8 0 0 1 0 11.4",
  review: "M8 3h8a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2ZM10 9l5 3-5 3z",
  money: "M12 2v20M17 6H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6",
  stats: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14ZM20 20l-4-4",
  bell: "M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8M10 21h4",
  coin: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM12 7v10M15 9.5c0-1.4-1.3-2-3-2s-3 .7-3 2 1.3 1.8 3 2.2 3 .9 3 2.3-1.3 2-3 2-3-.6-3-2",
  funnel: "M3 4h18l-7 8v6l-4 2v-8z",
  clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM12 7v5l3 2",
  trend: "m3 17 6-6 4 4 8-8M15 7h6v6",
  edit: "M4 20h4L19 9l-4-4L4 16zM14 6l4 4",
  download: "M12 3v12m-5-5 5 5 5-5M4 21h16",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  send: "m22 2-7 20-4-9-9-4z",
  trim: "M6 4v16M18 4v16M6 12h12",
  cap: "M4 6h16v12H4zM8 12h3M13 12h3M8 15h8",
  head: "M5 5h14M12 5v14",
  crop: "M7 3v14h14M3 7h14v14",
  fb: "M4 12a8 8 0 1 0 3-6.2M4 4v4h4",
  aud: "M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2",
  back: "M19 12H5M12 19l-7-7 7-7",
  x: "M18 6 6 18M6 6l12 12",
  check: "m5 12 5 5L20 7",
  play: "M7 4.5v15l12.5-7.5z",
  pause: "M8 5v14M16 5v14",
  vol: "M4 9v6h4l5 4V5L8 9zM16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12",
  mute: "M4 9v6h4l5 4V5L8 9zM17 9l5 6M22 9l-5 6",
  stepb: "M18 6v12l-8-6zM6 6v12",
  stepf: "M6 6v12l8-6zM18 6v12",
  split: "M12 3v18M7 8l-3 4 3 4M17 8l3 4-3 4",
  trash: "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
  restore: "M4 12a8 8 0 1 0 2.3-5.7M4 4v5h5",
  undo: "M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3",
  redo: "m15 14 5-5-5-5M20 9H9a5 5 0 0 0 0 10h3",
  plus: "M12 5v14M5 12h14",
  loop: "M17 2l4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 0 1-3 3H3",
  key: "M3 7h18v10H3zM7 11h.01M11 11h.01M15 11h.01M8 14h8",
  chat: "M4 5h16v11H8l-4 4z",
};
export function Ico({ n, size, sw = 2 }: { n: keyof typeof P | string; size?: number; sw?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth={sw}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={P[n] ?? ""} /></svg>
  );
}

const PLAT: Record<Platform | "twitch" | "kick", string> = {
  youtube: "M21.6 7.2a2.7 2.7 0 0 0-1.9-1.9C18 4.8 12 4.8 12 4.8s-6 0-7.7.5a2.7 2.7 0 0 0-1.9 1.9C2 8.9 2 12 2 12s0 3.1.4 4.8a2.7 2.7 0 0 0 1.9 1.9c1.7.5 7.7.5 7.7.5s6 0 7.7-.5a2.7 2.7 0 0 0 1.9-1.9c.4-1.7.4-4.8.4-4.8s0-3.1-.4-4.8ZM10 15.1V8.9l5.2 3.1Z",
  tiktok: "M16.6 3c.3 2.2 1.6 3.6 3.9 3.8v2.6a6.6 6.6 0 0 1-3.8-1.2v5.5c0 3.4-2.5 5.8-5.7 5.8a5.6 5.6 0 0 1-5.6-5.6c0-3.4 2.9-6 6.6-5.5v2.8c-1.6-.4-3.8.4-3.8 2.7 0 1.6 1.2 2.8 2.8 2.8 1.7 0 2.9-1.1 2.9-3.1V3Z",
  x: "M17.8 3h3l-6.6 7.6L22 21h-6.1l-4.8-6.3L5.6 21h-3l7.1-8.1L2.2 3h6.2l4.3 5.8Zm-1 16.2h1.7L7.3 4.7H5.5Z",
  twitch: "M4 3 3 6v13h4v2h3l2-2h3l5-5V3Zm15 10-3 3h-4l-2 2v-2H7V5h12ZM15 8h2v5h-2Zm-5 0h2v5h-2Z",
  kick: "",
};
export function PlatIco({ p, size = 14 }: { p: Platform | "twitch" | "kick"; size?: number }) {
  if (p === "kick") {
    return (
      <svg viewBox="0 0 24 24" width={size} height={size} aria-label="Kick"><rect width="24" height="24" rx="5" style={{ fill: "var(--kick)" }} />
        <path style={{ fill: "var(--stage)" }} d="M7 6h3v4h1l2-2h2v-2h3v4h-2v2h-2v2h2v2h2v4h-3v-2h-2l-2-2h-1v4H7Z" /></svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-label={p === "twitch" ? "Twitch" : undefined} aria-hidden={p === "twitch" ? undefined : true}>
      <path style={{ fill: p === "twitch" ? "var(--tw)" : "currentColor" }} d={PLAT[p]} />
    </svg>
  );
}

/** Hero / popup score dial (halo gradient arc). */
export function Dial({ score, size = 78 }: { score: number | null; size?: number }) {
  const r = size / 2 - 6, c = 2 * Math.PI * r, v = score ?? 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-label={score == null ? "No score yet" : `Grok score ${score}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" className="z-dtrk" strokeWidth={7} />
      {score != null && <circle cx={size / 2} cy={size / 2} r={r} fill="none" className="z-darc" strokeWidth={7} strokeLinecap="round"
        strokeDasharray={c.toFixed(1)} strokeDashoffset={(c * (1 - v / 100)).toFixed(1)} transform={`rotate(-90 ${size / 2} ${size / 2})`} />}
      <text x="50%" y="54%" textAnchor="middle" dominantBaseline="middle" className="z-dtxt" fontSize={Math.round(size * 0.28)}>{score ?? "—"}</text>
    </svg>
  );
}

/** Queue row ring in the streamer's colour. */
export function QRing({ score }: { score: number | null }) {
  const c = 2 * Math.PI * 15, v = score ?? 0;
  return (
    <svg className="z-qring" viewBox="0 0 38 38" aria-label={score == null ? "No score" : `Score ${score}`}>
      <circle cx="19" cy="19" r="15" fill="none" className="z-qrt" strokeWidth="3.5" />
      {score != null && <circle cx="19" cy="19" r="15" fill="none" className="z-qra" strokeWidth="3.5" strokeLinecap="round"
        strokeDasharray={c.toFixed(1)} strokeDashoffset={(c * (1 - v / 100)).toFixed(1)} transform="rotate(-90 19 19)" />}
      <text x="19" y="20" textAnchor="middle" dominantBaseline="middle">{score ?? "—"}</text>
    </svg>
  );
}

/** Gradient defs the dial and spend sparkline reference (once per page). */
export function SvgDefs() {
  return (
    <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden="true"><defs>
      <linearGradient id="hg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#bfe0ff" /><stop offset=".5" style={{ stopColor: "var(--halo)" }} /><stop offset="1" style={{ stopColor: "var(--vio)" }} /></linearGradient>
      <linearGradient id="sg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" style={{ stopColor: "var(--halo)", stopOpacity: 0.5 }} /><stop offset="1" style={{ stopColor: "var(--halo)", stopOpacity: 0 }} /></linearGradient>
    </defs></svg>
  );
}

/** Polyline path over a 0..w x 0..h box; values scaled to their own max. */
export function sparkPath(vals: number[], w: number, h: number, pad = 2): string {
  if (vals.length < 2) return "";
  const max = Math.max(...vals), min = Math.min(...vals), span = max - min || 1;
  return vals.map((v, i) => `${i ? "L" : "M"}${((i / (vals.length - 1)) * w).toFixed(1)} ${(h - pad - ((v - min) / span) * (h - pad * 2)).toFixed(1)}`).join(" ");
}

/** A private clip file as a short-lived signed URL (D056); null until it resolves or when there is none. */
export function useMedia(path: string | null | undefined): string | null {
  const { mediaUrl } = useStore();
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    setUrl(null);
    if (path) void mediaUrl(path).then((u) => { if (live) setUrl(u); });
    return () => { live = false; };
  }, [path, mediaUrl]);
  return url;
}
