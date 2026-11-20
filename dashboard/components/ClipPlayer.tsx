"use client";
import { useEffect, useState } from "react";
import { useStore } from "@/lib/store";
import type { Clip } from "@/lib/types";

/** 9:16 player fed by a short-lived signed link (D056). */
export function ClipPlayer({ clip, autoPlay = false }: { clip: Clip | null; autoPlay?: boolean }) {
  const { mediaUrl } = useStore();
  const [src, setSrc] = useState<string | null>(null);
  const [poster, setPoster] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    setSrc(null); setPoster(null); setFailed(false);
    if (!clip) return;
    void mediaUrl(clip.storage_path).then((u) => { if (live) { setSrc(u); setFailed(!u); } });
    void mediaUrl(clip.thumb_path).then((u) => live && setPoster(u));
    return () => { live = false; };
  }, [clip, mediaUrl]);
  return (
    <div className="vclip">
      {src
        ? <video key={src} src={src} poster={poster ?? undefined} controls playsInline autoPlay={autoPlay}
            muted={autoPlay} loop preload="metadata" />
        : <div className="vclip-empty">{!clip ? "Nothing to play" : failed ? "Clip file not found" : "Loading clip…"}</div>}
    </div>
  );
}
