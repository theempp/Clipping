"use client";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { mmss } from "@/lib/logic";
import { streamerHue } from "@/lib/view";
import { useStore } from "@/lib/store";
import type { Clip } from "@/lib/types";
import { Icon } from "./Icon";

/** The clip itself, playing muted in a 9:16 frame as soon as it is on screen (no click needed).
 *  Off screen it pauses, so a long queue never plays twenty videos at once. Tap the speaker for sound. */
/** `sound={false}` drops the mute toggle, for thumbnails that sit inside another button. */
export function ClipVideo({ clip, children, sound = true }: { clip: Clip; children?: React.ReactNode; sound?: boolean }) {
  const { mediaUrl } = useStore();
  const [src, setSrc] = useState<string | null>(null);
  const [poster, setPoster] = useState<string | null>(null);
  const [muted, setMuted] = useState(true);
  const box = useRef<HTMLDivElement>(null);
  const vid = useRef<HTMLVideoElement>(null);
  const [seen, setSeen] = useState(false);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) setSeen(true);
      const v = vid.current;
      if (!v) return;
      if (e.isIntersecting) void v.play().catch(() => {}); else v.pause();
    }, { threshold: 0.35 });
    io.observe(el);
    return () => io.disconnect();
  }, [src]);

  // Signed links (D056) are only requested once the card has been on screen.
  useEffect(() => {
    if (!seen) return;
    let live = true;
    void mediaUrl(clip.storage_path).then((u) => live && setSrc(u));
    void mediaUrl(clip.thumb_path).then((u) => live && setPoster(u));
    return () => { live = false; };
  }, [seen, clip.storage_path, clip.thumb_path, mediaUrl]);

  return (
    <div ref={box} className="cv" style={{ "--h": streamerHue(clip.channel_key.split(":")[1] ?? "") } as CSSProperties}>
      {src && (
        <video ref={vid} src={src} poster={poster ?? undefined} muted={muted} loop playsInline autoPlay preload="metadata"
          aria-label={`${clip.title ?? "Clip"} preview`} />
      )}
      {src && sound && (
        <button type="button" className="snd" aria-label={muted ? "Turn sound on" : "Mute"} onClick={(e) => { e.preventDefault(); setMuted((m) => !m); }}>
          <Icon name={muted ? "mute" : "vol"} size={14} />
        </button>
      )}
      {clip.duration_s != null && <span className="du">{mmss(clip.duration_s)}</span>}
      {children}
    </div>
  );
}
