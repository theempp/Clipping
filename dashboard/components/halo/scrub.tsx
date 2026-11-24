"use client";
// Shared player controls for the review hero and the review popup: drag-to-scrub timeline,
// frame step, speed, mute, keyboard. Pure playback: nothing here changes the clip.
import { useCallback, useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { readPrefs } from "@/lib/prefs";
import { Ico } from "./ui";

const FRAME = 1 / 30;
export const RATES = [0.5, 1, 1.25, 1.5, 2];
export const fmtT = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}.${Math.floor((s % 1) * 10)}`;

export type VideoCtl = {
  t: number; dur: number; paused: boolean; muted: boolean; rate: number; loop: boolean;
  toggle: () => void; seek: (s: number) => void; step: (d: number) => void;
  setMuted: (m: boolean) => void; cycleRate: () => void; toggleLoop: () => void;
  /** Scrub start/end: pauses while dragging, resumes if it was playing. */
  grab: () => void; release: () => void;
};

/** Live state of a <video>. `key` is whatever remounts the element (its src). */
export function useVideoCtl(ref: RefObject<HTMLVideoElement | null>, key: unknown, usePref = true): VideoCtl {
  const [t, setT] = useState(0);
  const [dur, setDur] = useState(0);
  const [paused, setPaused] = useState(true);
  const [muted, setMutedS] = useState(true);
  const [rate, setRate] = useState(1);
  const [loop, setLoop] = useState(true);
  const was = useRef(false);
  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    let raf = 0;
    const loop = () => { setT(v.currentTime); raf = requestAnimationFrame(loop); };
    const meta = () => setDur(Number.isFinite(v.duration) ? v.duration : 0);
    const play = () => { setPaused(false); cancelAnimationFrame(raf); raf = requestAnimationFrame(loop); };
    const pause = () => { setPaused(true); cancelAnimationFrame(raf); setT(v.currentTime); };
    const tick = () => setT(v.currentTime);
    // Settings > Player: speed, loop and sound. Sound falls back to muted if the browser blocks autoplay with sound.
    const pr = readPrefs();
    v.playbackRate = pr.rate; setRate(pr.rate);
    if (usePref) {
      v.loop = pr.loop; setLoop(pr.loop);
      v.muted = !pr.sound; setMutedS(!pr.sound);
      if (pr.sound && v.autoplay) void v.play().catch(() => { v.muted = true; setMutedS(true); void v.play().catch(() => {}); });
    }
    meta(); setPaused(v.paused); if (!v.paused) play();
    v.addEventListener("loadedmetadata", meta); v.addEventListener("durationchange", meta);
    v.addEventListener("play", play); v.addEventListener("pause", pause); v.addEventListener("seeked", tick);
    return () => {
      cancelAnimationFrame(raf);
      v.removeEventListener("loadedmetadata", meta); v.removeEventListener("durationchange", meta);
      v.removeEventListener("play", play); v.removeEventListener("pause", pause); v.removeEventListener("seeked", tick);
    };
  }, [ref, key]);
  const seek = useCallback((s: number) => { const v = ref.current; if (!v) return; const d = v.duration || 0; v.currentTime = Math.max(0, Math.min(d || s, s)); setT(v.currentTime); }, [ref]);
  const toggle = useCallback(() => { const v = ref.current; if (!v) return; if (v.paused) void v.play().catch(() => {}); else v.pause(); }, [ref]);
  const step = useCallback((d: number) => { const v = ref.current; if (!v) return; v.pause(); seek(v.currentTime + d); }, [ref, seek]);
  const setMuted = useCallback((m: boolean) => { const v = ref.current; if (v) v.muted = m; setMutedS(m); }, [ref]);
  const cycleRate = useCallback(() => { const v = ref.current; const r = RATES[(RATES.indexOf(v?.playbackRate ?? 1) + 1) % RATES.length]; if (v) v.playbackRate = r; setRate(r); }, [ref]);
  const grab = useCallback(() => { const v = ref.current; if (!v) return; was.current = !v.paused; v.pause(); }, [ref]);
  const release = useCallback(() => { const v = ref.current; if (v && was.current) void v.play().catch(() => {}); was.current = false; }, [ref]);
  const toggleLoop = useCallback(() => { const v = ref.current; const l = !(v?.loop ?? loop); if (v) v.loop = l; setLoop(l); }, [ref, loop]);
  return { t, dur, paused, muted, rate, loop, toggle, seek, step, setMuted, cycleRate, toggleLoop, grab, release };
}

/** Keyboard for a player: Space/K play, J/L or arrows ±1 s (Shift ±5 s), , . frame, M mute, Home/End. */
export function playerKeys(ctl: VideoCtl, e: { key: string; shiftKey: boolean; preventDefault: () => void }): boolean {
  const big = e.shiftKey ? 5 : 1;
  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  const map: Record<string, () => void> = {
    " ": ctl.toggle, k: ctl.toggle,
    ArrowLeft: () => ctl.seek(ctl.t - big), j: () => ctl.seek(ctl.t - big),
    ArrowRight: () => ctl.seek(ctl.t + big), l: () => ctl.seek(ctl.t + big),
    ",": () => ctl.step(-FRAME), ".": () => ctl.step(FRAME),
    m: () => ctl.setMuted(!ctl.muted), Home: () => ctl.seek(0), End: () => ctl.seek(ctl.dur),
  };
  const f = map[k];
  if (!f) return false;
  e.preventDefault(); f();
  return true;
}

/** Drag-to-scrub timeline with hover time, optional hook band, and a control row. */
export function Scrubber({ ctl, hook, compact = false }: { ctl: VideoCtl; hook?: [number, number] | null; compact?: boolean }) {
  const track = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [drag, setDrag] = useState(false);
  const d = ctl.dur || 0;
  const at = (x: number) => { const r = track.current?.getBoundingClientRect(); return r && d ? Math.max(0, Math.min(1, (x - r.left) / r.width)) * d : 0; };
  const pct = (s: number) => `${d ? (s / d) * 100 : 0}%`;
  return (
    <div className={`z-scrub${compact ? " z-cmp" : ""}${drag ? " z-drag" : ""}`}>
      <div ref={track} className="z-strack" role="slider" tabIndex={0} aria-label="Seek" aria-valuemin={0} aria-valuemax={Math.round(d * 10) / 10}
        aria-valuenow={Math.round(ctl.t * 10) / 10} aria-valuetext={`${fmtT(ctl.t)} of ${fmtT(d)}`}
        onKeyDown={(e) => { playerKeys(ctl, e); e.stopPropagation(); }}
        onPointerDown={(e) => { if (!d) return; e.preventDefault(); e.currentTarget.setPointerCapture(e.pointerId); e.currentTarget.focus(); ctl.grab(); setDrag(true); ctl.seek(at(e.clientX)); }}
        onPointerMove={(e) => { const s = at(e.clientX); setHover(s); if (drag) ctl.seek(s); }}
        onPointerUp={() => { if (drag) { setDrag(false); ctl.release(); } }}
        onPointerCancel={() => { if (drag) { setDrag(false); ctl.release(); } }}
        onPointerLeave={() => !drag && setHover(null)}>
        <span className="z-sbg" />
        {hook && d > 0 && <span className="z-shook" style={{ left: pct(hook[0]), width: pct(Math.max(0.2, hook[1] - hook[0])) }} title="Hook window" />}
        <span className="z-sfill" style={{ width: pct(ctl.t) }} />
        <span className="z-sknob" style={{ left: pct(ctl.t) }} />
        {hover != null && d > 0 && <span className="z-stip" style={{ left: pct(hover) }}>{fmtT(hover)}</span>}
      </div>
      <div className="z-srow">
        <button type="button" className="z-fstep" aria-label="Back one frame" title="Back one frame ( , )" onClick={() => ctl.step(-FRAME)}><Ico n="stepb" size={14} /></button>
        <button type="button" className="z-splay" aria-label={ctl.paused ? "Play" : "Pause"} title="Play / pause (Space)" onClick={ctl.toggle}>
          <Ico n={ctl.paused ? "play" : "pause"} size={15} sw={2.4} /></button>
        <button type="button" className="z-fstep" aria-label="Forward one frame" title="Forward one frame ( . )" onClick={() => ctl.step(FRAME)}><Ico n="stepf" size={14} /></button>
        <span className="z-stime z-mono">{fmtT(ctl.t)}<i> / {fmtT(d)}</i></span>
        <span className="z-sp" />
        {hook && !compact && <button type="button" className="z-stxt" title="Jump to the hook" onClick={() => ctl.seek(hook[0])}>Hook</button>}
        <button type="button" className={ctl.loop ? "z-son" : ""} aria-pressed={ctl.loop} aria-label="Loop" title={ctl.loop ? "Looping · click to play once" : "Plays once · click to loop"} onClick={ctl.toggleLoop}><Ico n="loop" size={13} /></button>
        <button type="button" className="z-stxt" aria-label={`Speed ${ctl.rate}x`} title="Playback speed" onClick={ctl.cycleRate}>{ctl.rate}x</button>
        <button type="button" aria-label={ctl.muted ? "Sound on" : "Sound off"} title="Sound (M)" onClick={() => ctl.setMuted(!ctl.muted)}>
          <Ico n={ctl.muted ? "mute" : "vol"} size={15} /></button>
      </div>
    </div>
  );
}

/** "0:02-0:05" -> [2, 5]; null when the judge gave none. */
export function hookRange(w: unknown): [number, number] | null {
  if (typeof w !== "string") return null;
  const m = w.match(/^(\d+):(\d{2})\s*[-–]\s*(\d+):(\d{2})/);
  if (!m) return null;
  return [Number(m[1]) * 60 + Number(m[2]), Number(m[3]) * 60 + Number(m[4])];
}
