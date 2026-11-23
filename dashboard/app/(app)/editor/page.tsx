"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { ClipVideo } from "@/components/ClipCard";
import { Icon } from "@/components/Icon";
import { clampTrim, droppedCuts, editNote, emphasisWords, mmss, pieces, rankQueue } from "@/lib/logic";
import { useStore } from "@/lib/store";
import type { Clip, EditPlan } from "@/lib/types";

export default function EditorPage() {
  return <Suspense fallback={<div className="loading">Loading…</div>}><Editor /></Suspense>;
}

type Tool = "trim" | "split" | "cap";
const CROP_W = 0.316; // a 9:16 window is 31.6% of a 16:9 frame

function hashSeed(s: string) { let h = 7; for (const c of s) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h || 7; }

/** Manual editor, trim and captions first (D098): pick a clip, drag the trim handles, move the crop box,
 *  fix the headline and captions, then send it back to the PC as a revision. */
function Editor() {
  const { snap, mediaUrl, sendEdit } = useStore();
  const params = useSearchParams();
  const router = useRouter();
  const queue = useMemo(() => rankQueue(snap.clips), [snap.clips]);
  const [who, setWho] = useState<string | "all">("all");
  const bin = queue.filter((c) => who === "all" || c.streamer_id === who);
  const clip: Clip | null = snap.clips.find((c) => c.id === params.get("clip")) ?? queue[0] ?? null;
  const editable = clip?.state === "pending_review";

  const total = Math.max(1, clip?.duration_s ?? 30);
  const fresh = useCallback((): EditPlan => ({
    trim_in: 0, trim_out: total, crop_x: 0.5, zoom: 1.12,
    headline: clip?.title ?? "", caption_style: "words", splits: [], drop: [],
    emphasis_words: emphasisWords((clip?.hook ?? clip?.title ?? "").split(/\s+/).slice(0, 3).join(" ")),
  }), [clip?.id, clip?.title, clip?.hook, total]); // eslint-disable-line react-hooks/exhaustive-deps
  const [plan, setPlan] = useState<EditPlan>(fresh);
  const [hist, setHist] = useState<EditPlan[]>([]);
  const [tool, setTool] = useState<Tool>("trim");
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [capText, setCapText] = useState("");
  const [sent, setSent] = useState<"" | "sending" | "sent" | "failed">("");
  const [src, setSrc] = useState<{ clip: string | null; source: string | null }>({ clip: null, source: null });
  const vid = useRef<HTMLVideoElement>(null);
  const srcVid = useRef<HTMLVideoElement>(null);
  const tl = useRef<HTMLDivElement>(null);
  const srcBox = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const f0 = fresh();
    setPlan(f0); setCapText(f0.emphasis_words.join(" ").toUpperCase()); setHist([]); setT(0); setPlaying(false); setSent("");
    let live = true;
    setSrc({ clip: null, source: null });
    if (clip) void Promise.all([mediaUrl(clip.storage_path), mediaUrl(clip.source_path ?? null)])
      .then(([a, b]) => live && setSrc({ clip: a, source: b }));
    return () => { live = false; };
  }, [clip?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const change = (p: Partial<EditPlan>) => { setHist((h) => [...h.slice(-30), plan]); setPlan((x) => ({ ...x, ...p })); setSent(""); };
  const undo = () => setHist((h) => {
    if (!h.length) return h;
    const prev = h[h.length - 1];
    setPlan(prev); setCapText(prev.emphasis_words.join(" ").toUpperCase());
    return h.slice(0, -1);
  });

  // The preview shows the stream window cropped live when the 16:9 copy exists, else the rendered clip.
  const preview = src.source ?? src.clip;
  const cropped = !!src.source;

  // Keep playback inside the trim.
  useEffect(() => {
    const v = vid.current;
    if (!v) return;
    const tick = () => {
      if (v.currentTime >= plan.trim_out || v.currentTime < plan.trim_in - 0.05) v.currentTime = plan.trim_in;
      setT(v.currentTime);
      const s = srcVid.current;
      if (s && Math.abs(s.currentTime - v.currentTime) > 0.2) s.currentTime = v.currentTime;
    };
    v.addEventListener("timeupdate", tick);
    return () => v.removeEventListener("timeupdate", tick);
  }, [plan.trim_in, plan.trim_out, preview]);

  const toggle = () => {
    const v = vid.current;
    if (!v) return;
    if (v.paused) { if (v.currentTime < plan.trim_in || v.currentTime >= plan.trim_out) v.currentTime = plan.trim_in; void v.play(); setPlaying(true); }
    else { v.pause(); setPlaying(false); }
  };
  const seek = (s: number) => { setT(s); if (vid.current) vid.current.currentTime = s; if (srcVid.current) srcVid.current.currentTime = s; };

  // Pointer helpers: fraction of the timeline / source box under the pointer.
  const frac = (el: HTMLElement | null, x: number) => {
    const r = el?.getBoundingClientRect();
    return r ? Math.max(0, Math.min(1, (x - r.left) / r.width)) : 0;
  };
  const drag = (kind: "in" | "out" | "ph") => (e: React.PointerEvent) => {
    e.preventDefault(); e.stopPropagation();
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    const before = plan;
    let last = plan;
    const move = (ev: PointerEvent) => {
      const s = frac(tl.current, ev.clientX) * total;
      if (kind === "ph") { seek(s); return; }
      const [a, b] = kind === "in" ? clampTrim(s, last.trim_out, total) : clampTrim(last.trim_in, s, total);
      last = { ...last, trim_in: a, trim_out: b };
      setPlan(last);
      seek(kind === "in" ? a : b);
    };
    const up = () => {
      el.removeEventListener("pointermove", move); el.removeEventListener("pointerup", up); el.removeEventListener("pointercancel", up);
      if (kind !== "ph" && (last.trim_in !== before.trim_in || last.trim_out !== before.trim_out)) { setHist((h) => [...h.slice(-30), before]); setSent(""); }
    };
    el.addEventListener("pointermove", move); el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
  };
  const clickTl = (e: React.PointerEvent) => {
    const s = +(frac(tl.current, e.clientX) * total).toFixed(2);
    if (tool === "split") { if (s > plan.trim_in && s < plan.trim_out) change({ splits: [...plan.splits, s].sort((a, b) => a - b) }); return; }
    seek(s);
  };
  const dragCrop = (e: React.PointerEvent) => {
    e.preventDefault();
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    const before = plan;
    const r = srcBox.current?.getBoundingClientRect();
    const start = e.clientX, from = plan.crop_x;
    let last = from;
    const move = (ev: PointerEvent) => {
      if (!r) return;
      last = Math.max(CROP_W / 2, Math.min(1 - CROP_W / 2, from + (ev.clientX - start) / r.width));
      setPlan((p) => ({ ...p, crop_x: +last.toFixed(3) }));
    };
    const up = () => {
      el.removeEventListener("pointermove", move); el.removeEventListener("pointerup", up); el.removeEventListener("pointercancel", up);
      if (last !== from) { setHist((h) => [...h.slice(-30), before]); setSent(""); }
    };
    el.addEventListener("pointermove", move); el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
  };
  const nudgeCrop = (d: number) => change({ crop_x: +Math.max(CROP_W / 2, Math.min(1 - CROP_W / 2, plan.crop_x + d)).toFixed(3) });

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el.closest("input,textarea,select,[contenteditable]")) return;
      if (e.key === " ") { e.preventDefault(); toggle(); }
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); undo(); }
      else if (e.key === "[") change({ trim_in: clampTrim(t, plan.trim_out, total)[0] });
      else if (e.key === "]") change({ trim_out: clampTrim(plan.trim_in, t, total)[1] });
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  const send = async () => {
    if (!clip || !editable) return;
    setSent("sending");
    const ok = await sendEdit(clip, plan, fresh());
    setSent(ok ? "sent" : "failed");
  };

  const wave = useMemo(() => {
    const real = clip?.manifest?.peaks;  // measured by the PC at render time
    if (Array.isArray(real) && real.length > 8 && real.every((v) => typeof v === "number")) return real as number[];
    let s = hashSeed(clip?.id ?? "x");
    return Array.from({ length: 90 }, () => { s = (s * 16807) % 2147483647; return 15 + (s / 2147483647) * 85; });
  }, [clip?.id, clip?.manifest]);
  const words = capText.split(/\s+/).filter(Boolean);
  const pct = (s: number) => `${(s / total) * 100}%`;
  const len = plan.trim_out - plan.trim_in;
  const kept = len - droppedCuts(plan).reduce((s, [a, b]) => s + b - a, 0);

  if (!clip) {
    return (
      <section className="glass">
        <h2 style={{ marginTop: 0, font: "600 22px var(--fd)" }}>Nothing to edit yet</h2>
        <p className="mut">Clips waiting for review open here for trim, crop, headline and captions.</p>
        <Link href="/library" className="b ok">Open the library</Link>
      </section>
    );
  }

  return (
    <>
      <div className="edst" style={{ "--cx": `${((plan.crop_x - CROP_W / 2) / (1 - CROP_W)) * 100}%`, "--z": plan.zoom } as CSSProperties}>
        <div className="fpanel">
          <div className="hd">
            <h3>Clips</h3>
            <select className="in" style={{ width: "auto", padding: "4px 10px", fontSize: 11 }} value={who} onChange={(e) => setWho(e.target.value)} aria-label="Streamer filter">
              <option value="all">Everyone</option>
              {snap.streamers.filter((s) => queue.some((c) => c.streamer_id === s.id)).map((s) => <option key={s.id} value={s.id}>{s.display_name}</option>)}
            </select>
          </div>
          <div className="bin">
            {bin.slice(0, 6).map((c) => (
              <button key={c.id} type="button" className={c.id === clip.id ? "on" : ""} aria-label={`Edit ${c.title ?? c.job_id}`}
                onClick={() => router.replace(`/editor?clip=${c.id}`, { scroll: false })}>
                <ClipVideo clip={c} sound={false} />
              </button>
            ))}
          </div>
          {bin.length === 0 && <p className="quiet">No clips waiting.</p>}
          <div className="mut" style={{ fontSize: 12, marginTop: 14 }}>Crop box · drag{cropped ? "" : " (needs the stream copy)"}</div>
          <div ref={srcBox} className="src">
            {src.source
              ? <video ref={srcVid} src={src.source} muted playsInline preload="metadata" />
              : <div className="vclip-empty" style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center" }}>No 16:9 copy for this clip</div>}
            {src.source && (
              <div className="cropbox" role="slider" tabIndex={0} aria-label="Crop position" aria-valuemin={0} aria-valuemax={100}
                aria-valuenow={Math.round(plan.crop_x * 100)} style={{ left: `${(plan.crop_x - CROP_W / 2) * 100}%` }}
                onPointerDown={dragCrop}
                onKeyDown={(e) => { if (e.key === "ArrowLeft") nudgeCrop(-0.02); if (e.key === "ArrowRight") nudgeCrop(0.02); }} />
            )}
          </div>
        </div>

        <div className="center">
          <div className="vid">
            {preview
              ? <video ref={vid} src={preview} playsInline preload="metadata" muted={cropped} onPause={() => setPlaying(false)} onPlay={() => setPlaying(true)}
                  style={cropped ? undefined : { objectFit: "contain" }} />
              : <div className="vclip-empty" style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center" }}>Loading clip…</div>}
            {plan.headline.trim() && <div className="headl">{plan.headline}</div>}
            {words.length > 0 && (
              <div className={`cap${plan.caption_style === "line" ? " line" : ""}`}>
                {plan.caption_style === "words"
                  ? <>{words.slice(0, -1).join(" ")} <span>{words[words.length - 1]}</span></>
                  : capText}
              </div>
            )}
          </div>
          <div className="ctrl">
            <button type="button" className="playbtn" aria-label={playing ? "Pause" : "Play"} onClick={toggle}><Icon name={playing ? "pause" : "play"} size={18} /></button>
            <span>{mmss(t)} / {mmss(total)}</span>
          </div>
        </div>

        <div className="fpanel">
          <label className="field">Headline
            <input type="text" value={plan.headline} maxLength={90} onChange={(e) => setPlan((p) => ({ ...p, headline: e.target.value }))}
              onBlur={() => setHist((h) => [...h.slice(-30), plan])} /></label>
          <label className="field">Emphasis words
            <input type="text" value={capText} maxLength={60} onChange={(e) => { const v = e.target.value.toUpperCase(); setCapText(v); setPlan((p) => ({ ...p, emphasis_words: emphasisWords(v) })); setSent(""); }}
              onBlur={() => setHist((h) => [...h.slice(-30), plan])} /></label>
          <label className="field">Captions
            <select value={plan.caption_style} onChange={(e) => change({ caption_style: e.target.value as EditPlan["caption_style"] })}>
              <option value="words">2-3 words · emphasis</option>
              <option value="line">Full line</option>
            </select></label>
          <label className="field">Zoom <b>{Math.round(plan.zoom * 100)}%</b>
            <input type="range" min={100} max={130} value={Math.round(plan.zoom * 100)}
              onChange={(e) => setPlan((p) => ({ ...p, zoom: Number(e.target.value) / 100 }))} /></label>
          <button type="button" className="b ok wide lg" disabled={!editable || sent === "sending" || sent === "sent"} onClick={() => void send()}>
            {sent === "sending" ? "Sending…" : sent === "sent" ? "Sent to the PC" : "Send to review"}
          </button>
          <p className="quiet" style={{ fontSize: 11 }}>
            {!editable ? `This clip is ${clip.state.replace("_", " ")}; only clips waiting for review can be re-edited.`
              : sent === "sent" ? "The PC re-renders it and it comes back to Review."
              : sent === "failed" ? "Did not send. See the error at the top."
              : editNote(plan, fresh())}
          </p>
        </div>

        <div className="tdock">
          <div className="tools">
            <button type="button" className={tool === "trim" ? "on" : ""} onClick={() => setTool("trim")}><Icon name="crop" size={14} />Trim</button>
            <button type="button" className={tool === "split" ? "on" : ""} onClick={() => setTool("split")} title="Click the timeline to cut there"><Icon name="cut" size={14} />Split</button>
            <button type="button" className={tool === "cap" ? "on" : ""} onClick={() => setTool("cap")}><Icon name="type" size={14} />Caption</button>
            <button type="button" disabled={!hist.length} onClick={undo}><Icon name="undo" size={14} />Undo</button>
            {plan.splits.length > 0 && <button type="button" onClick={() => change({ splits: [], drop: [] })}>Clear {plan.splits.length} split{plan.splits.length === 1 ? "" : "s"}</button>}
            {plan.splits.length > 0 && pieces(plan).map(([a, b]) => {
              const off = (plan.drop ?? []).includes(a);
              return (
                <button key={a} type="button" className={off ? "" : "on"} aria-pressed={!off}
                  title={off ? "Dropped: the PC cuts this piece out" : "Kept"}
                  onClick={() => change({ drop: off ? (plan.drop ?? []).filter((x) => x !== a) : [...(plan.drop ?? []), a] })}>
                  {off ? "Drop" : "Keep"} {a.toFixed(1)}–{b.toFixed(1)}s
                </button>
              );
            })}
            <span className="sp" />
            <span className="mut" style={{ fontSize: 12 }}>Selected <b style={{ color: "var(--tx)" }} className="tnum">{kept.toFixed(1)}s</b></span>
          </div>
          <div className="tl" ref={tl} onPointerDown={clickTl} role="group" aria-label="Timeline">
            <div className="ruler" />
            <div className="trk main">
              <div className="clipbar" style={{ left: pct(plan.trim_in), width: `calc(${pct(len)})` }}>
                <button type="button" className="hdl l" aria-label={`Trim start ${plan.trim_in.toFixed(1)} seconds`} onPointerDown={drag("in")}
                  onKeyDown={(e) => { if (e.key === "ArrowLeft" || e.key === "ArrowRight") change({ trim_in: clampTrim(plan.trim_in + (e.key === "ArrowLeft" ? -0.5 : 0.5), plan.trim_out, total)[0] }); }} />
                <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{clip.title ?? clip.job_id} · {len.toFixed(1)} s</span>
                <button type="button" className="hdl r" aria-label={`Trim end ${plan.trim_out.toFixed(1)} seconds`} onPointerDown={drag("out")}
                  onKeyDown={(e) => { if (e.key === "ArrowLeft" || e.key === "ArrowRight") change({ trim_out: clampTrim(plan.trim_in, plan.trim_out + (e.key === "ArrowLeft" ? -0.5 : 0.5), total)[1] }); }} />
              </div>
              {plan.splits.map((s) => <i key={s} className="splitm" style={{ left: pct(s) }} title={`split at ${s.toFixed(1)}s`} />)}
              {droppedCuts(plan).map(([a, b]) => <i key={`d${a}`} className="dropm" style={{ left: pct(a), width: pct(b - a) }} aria-hidden="true" />)}
            </div>
            <div className="trk"><div className="wav">{wave.map((h, i) => <i key={i} style={{ height: `${h}%` }} />)}</div></div>
            <div className="trk ctk">
              {words.length > 0 && <span style={{ left: pct(plan.trim_in + len * 0.12) }}>{capText}</span>}
              {plan.headline && <span style={{ left: pct(plan.trim_in + len * 0.5), background: "#ffffff1c", color: "var(--tx)" }}>{plan.headline}</span>}
            </div>
            <div className="ph" style={{ left: pct(t) }} onPointerDown={drag("ph")} />
          </div>
          <p className="quiet" style={{ fontSize: 11, marginBottom: 0 }}>Space plays · drag the white handles to trim · <kbd>[</kbd> <kbd>]</kbd> set in/out at the playhead · Split, click the timeline, then Keep/Drop each piece · Ctrl+Z undo</p>
        </div>
      </div>
    </>
  );
}
