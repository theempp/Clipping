import { initials } from "@/lib/logic";
import type { Streamer } from "@/lib/types";
import { avatarBg } from "@/lib/view";

export function Avatar({ s, live, size = 34 }: { s: Streamer; live?: boolean; size?: number }) {
  return (
    <span className={`av${live ? " lv" : ""}`} style={{ width: size, height: size, background: avatarBg(s.slug) }}>
      {s.avatar_url
        // eslint-disable-next-line @next/next/no-img-element
        ? <img src={s.avatar_url} alt="" referrerPolicy="no-referrer" />
        : initials(s.display_name)}
    </span>
  );
}
