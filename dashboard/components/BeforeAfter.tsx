"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useStore } from "@/lib/store";
import type { Clip } from "@/lib/types";
import { Icon } from "./Icon";

/** Before (the untouched 16:9 stream window) next to after (the vertical clip), D077.
 *  "Play both" starts them together from the top and keeps them in step. */
export function BeforeAfter({ clip, children }: { clip: Clip | null; children?: ReactNode }) {
  const { mediaUrl } = useStore();
  const [src, setSrc] = useState<{ before: string | null; after: string | null; poster: string | null }>({ before: null, after: null, poster: null });
  const [loaded, setLoaded] = useState(false);
  const [synced, setSynced] = useState(false);
  const b = useRef<HTMLVideoElement>(null);
  const a = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    let live = true;
    setLoaded(false); setSynced(false);
    setSrc({ before: null, after: null, poster: null });
    if (!clip) return;
    void Promise.all([mediaUrl(clip.source_path ?? null), mediaUrl(clip.storage_path), mediaUrl(clip.thumb_path)])
      .then(([before, after, poster]) => { if (live) { setSrc({ before, after, poster }); setLoaded(true); } });
    return () => { live = false; };
  }, [clip, mediaUrl]);

  // While synced, the "before" follows the "after" (the one with sound).
  useEffect(() => {
    const av = a.current, bv = b.current;
    if (!synced || !av || !bv) return;
    const follow = () => { if (Math.abs(bv.currentTime - av.currentTime) > 0.15) bv.currentTime = av.currentTime; };
    const play = () => void bv.play().catch(() => {});
    const pause = () => bv.pause();
    av.addEventListener("timeupdate", follow); av.addEventListener("seeked", follow);
    av.addEventListener("play", play); av.addEventListener("pause", pause);
    return () => {
      av.removeEventListener("timeupdate", follow); av.removeEventListener("seeked", follow);
      av.removeEventListener("play", play); av.removeEventListener("pause", pause);
    };
  }, [synced, src]);

  const playBoth = () => {
    const av = a.current, bv = b.current;
    if (!av) return;
    setSynced(true);
    av.currentTime = 0;
    if (bv) { bv.muted = true; bv.currentTime = 0; void bv.play().catch(() => {}); }
    void av.play().catch(() => {});
  };

  return (
    <div className="ba">
      <div className="ba-bar">
        <span className="r">Before → after</span>
        <button type="button" className={`b${synced ? " ok" : ""}`} disabled={!src.after} onClick={playBoth}>
          <Icon name="play" /> {synced ? "Playing in sync" : "Play both"}
        </button>
      </div>
      <figure className="ba-before">
        <figcaption><i className="k-before" />Before · stream 16:9</figcaption>
        <div className="screen16">
          {src.before
            ? <video ref={b} key={src.before} src={`${src.before}#t=0.5`} controls playsInline preload="metadata" muted={synced} />
            : <div className="vclip-empty">{!clip ? "Nothing to play" : !loaded ? "Loading…"
                : "No stream copy for this clip yet. Clips rendered from now on include one."}</div>}
        </div>
      </figure>
      {children && <div className="ba-side">{children}</div>}
      <figure className="ba-after">
        <figcaption><i className="k-after" />After · Clipp 9:16{clip?.revision ? ` · rev ${clip.revision}` : ""}</figcaption>
        <div className="vclip">
          {src.after
            ? <video ref={a} key={src.after} src={src.after} poster={src.poster ?? undefined} controls playsInline loop preload="metadata" />
            : <div className="vclip-empty">{!clip ? "Nothing to play" : !loaded ? "Loading clip…" : "Clip file not found"}</div>}
        </div>
      </figure>
    </div>
  );
}
