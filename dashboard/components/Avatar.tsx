"use client";
import { useEffect, useState } from "react";
import { initials } from "@/lib/logic";
import type { Streamer } from "@/lib/types";
import { avatarBg, avatarFallback } from "@/lib/view";

/** Real profile picture: the platform avatar (Twitch Helix / Kick via /api/live), then a public mirror,
 *  then initials on the streamer's gradient. A broken link drops to the next one. */
export function Avatar({ s, live, size = 34 }: { s: Streamer; live?: boolean; size?: number }) {
  const chain = [s.avatar_url, avatarFallback(s)].filter((x): x is string => !!x);
  const [i, setI] = useState(0);
  useEffect(() => setI(0), [s.avatar_url, s.slug]);
  const src = chain[i];
  return (
    <span className={`av${live ? " lv" : ""}`} style={{ width: size, height: size, background: avatarBg(s.slug), fontSize: Math.round(size * 0.36) }}>
      {initials(s.display_name)}
      {src && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" referrerPolicy="no-referrer" loading="lazy" onError={() => setI((x) => x + 1)} />
      )}
    </span>
  );
}
