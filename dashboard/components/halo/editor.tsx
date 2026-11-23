"use client";
// Edit clip (D116): takes over the main area, bars stay. Tools: Trim, Captions, Headline, Crop, Flashback, Audio.
// No zoom tool (D112). Save sends only what changed as a revision (kind "trim", payload.edit), which the PC
// re-renders and the learn loop reads as a manual edit (D114). Nothing here posts.
import { useEffect, useMemo, useRef, useState } from "react";
import { TOOL_LABEL, clampTrim, clipRecipe, editNote, editPayload, emphasisWords } from "@/lib/logic";
import { useStore } from "@/lib/store";
import type { Clip, EditPlan } from "@/lib/types";
import { basePlan, hookStart } from "@/lib/halo";
import { useReview } from "./review";
import { Ico, useMedia } from "./ui";

type Tool = "trim" | "cap" | "head" | "crop" | "fb" | "aud";
const TOOLS: [Tool, string, string][] = [["trim", "Trim", "trim"], ["cap", "Captions", "cap"], ["head", "Headline", "head"], ["crop", "Crop", "crop"], ["fb", "Flashback", "fb"], ["aud", "Audio", "aud"]];
const CROP_W = 0.316; // a 9:16 window is 31.6% of a 16:9 frame
const AUDIO_TOOLS = ["music_cue", "sfx_whoosh", "sfx_hit", "sfx_glitch"];

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}.${Math.floor((s % 1) * 10)}`;
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

export function Editor({ clip }: { clip: Clip }) {
  const { sendEdit, canReview, snap } = useStore();
  const ui = useReview();
  const base = useMemo(() => basePlan(clip), [clip.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const [plan, setPlan] = useState<EditPlan>(() => ({ ...base, headline: ui.draft(clip) || base.headline }));
  const [hist, setHist] = useState<EditPlan[]>([]);
  const [tool, setTool] = useState<Tool>("trim");
  const [t, setT] = useState(0);
  const [paused, setPaused] = useState(false);
  const [busy, setBusy] = useState(false);
  const [capText, setCapText] = useState(base.emphasis_words.join(" ").toUpperCase());
  const src = useMedia(clip.storage_path);
  const poster = useMedia(clip.thumb_path);
  const source = useMedia(clip.source_path ?? null);
  const vid = useRef<HTMLVideoElement>(null);
  const lane = useRef<HTMLDivElement>(null);
  const srcBox = useRef<HTMLDivElement>(null);
  const total = Math.max(1, clip.duration_s ?? 30);
  const recipe = clipRecipe(clip);
  const editable = clip.state === "pending_review" && canReview(clip);
  const changes = editPayload(plan, base);
  const dirty = Object.keys(changes).length > 0;
  const who = snap.streamers.find((s) => s.id === clip.streamer_id)?.display_name ?? clip.channel_key.split(":")[1];

  const change = (p: Partial<EditPlan>) => { setHist((h) => [...h.slice(-30), plan]); setPlan((x) => ({ ...x, ...p })); };
  const undo = () => setHist((h) => { if (!h.length) return h; const prev = h[h.length - 1]; setPlan(prev); setCapText(prev.emphasis_words.join(" ").toUpperCase()); return h.slice(0, -1); });

  // Keep playback inside the trim.
  useEffect(() => {
    const v = vid.current;
    if (!v) return;
    const tick = () => { if (v.currentTime >= plan.trim_out || v.currentTime < plan.trim_in - 0.05) v.currentTime = plan.trim_in; setT(v.currentTime); };
    v.addEventListener("timeupdate", tick);
    return () => v.removeEventListener("timeupdate", tick);
  }, [plan.trim_in, plan.trim_out, src]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el.closest("input,textarea,select,[contenteditable]")) return;
      if (e.key === " ") { e.preventDefault(); toggle(); }
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); undo(); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  const toggle = () => { const v = vid.current; if (!v) return; if (v.paused) { void v.play(); setPaused(false); } else { v.pause(); setPaused(true); } };
  const frac = (el: HTMLElement | null, x: number) => { const r = el?.getBoundingClientRect(); return r ? Math.max(0, Math.min(1, (x - r.left) / r.width)) : 0; };
  const dragTrim = (kind: "a" | "b") => (e: React.PointerEvent) => {
    if (!editable) return;
    e.preventDefault(); e.stopPropagation();
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    const before = plan;
    let last = plan;
    const move = (ev: PointerEvent) => {
      const s = frac(lane.current, ev.clientX) * total;
      const [a, b] = kind === "a" ? clampTrim(s, last.trim_out, total) : clampTrim(last.trim_in, s, total);
      last = { ...last, trim_in: a, trim_out: b };
      setPlan(last);
      if (vid.current) vid.current.currentTime = kind === "a" ? a : Math.max(a, b - 0.5);
    };
    const up = () => {
      el.removeEventListener("pointermove", move); el.removeEventListener("pointerup", up); el.removeEventListener("pointercancel", up);
      if (last.trim_in !== before.trim_in || last.trim_out !== before.trim_out) setHist((h) => [...h.slice(-30), before]);
    };
    el.addEventListener("pointermove", move); el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
  };
  const seek = (e: React.PointerEvent) => { const v = vid.current; if (v) v.currentTime = frac(lane.current, e.clientX) * total; };
  const dragCrop = (e: React.PointerEvent) => {
    if (!editable) return;
    e.preventDefault();
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    const before = plan, r = srcBox.current?.getBoundingClientRect(), start = e.clientX, from = plan.crop_x;
    let last = from;
    const move = (ev: PointerEvent) => { if (!r) return; last = Math.max(CROP_W / 2, Math.min(1 - CROP_W / 2, from + (ev.clientX - start) / r.width)); setPlan((p) => ({ ...p, crop_x: +last.toFixed(3) })); };
    const up = () => { el.removeEventListener("pointermove", move); el.removeEventListener("pointerup", up); el.removeEventListener("pointercancel", up); if (last !== from) setHist((h) => [...h.slice(-30), before]); };
    el.addEventListener("pointermove", move); el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
  };

  const save = async () => {
    if (!dirty) { ui.closeEditor(null); ui.toast("No changes. Back to review."); return; }
    if (!editable) return;
    setBusy(true);
    const ok = await sendEdit(clip, plan, base);
    setBusy(false);
    if (!ok) return;
    ui.setDraft(clip.id, plan.headline);
    ui.closeEditor(clip);
    ui.toast("Saved. The PC re-renders it; post once it is back.");
  };

  const peaks = clip.manifest?.peaks;
  const wave = Array.isArray(peaks) && peaks.length > 8 && peaks.every((v) => typeof v === "number") ? (peaks as number[]) : null;
  const words = capText.split(/\s+/).filter(Boolean);
  const len = plan.trim_out - plan.trim_in;
  const hs = hookStart(clip);
  const pct = (s: number) => `${(s / total) * 100}%`;
  const audioTools = (recipe?.tools ?? []).filter((x) => AUDIO_TOOLS.includes(x));
  const otherTools = (recipe?.tools ?? []).filter((x) => !AUDIO_TOOLS.includes(x));
  const toolBtn = (x: string) => {
    const off = (plan.remove_tools ?? []).includes(x);
    return (
      <button key={x} type="button" className={off ? "" : "z-on"} aria-pressed={!off} disabled={!editable}
        onClick={() => change({ remove_tools: off ? (plan.remove_tools ?? []).filter((y) => y !== x) : [...(plan.remove_tools ?? []), x] })}>
        {off ? "Off" : "On"} · {TOOL_LABEL[x] ?? x}</button>
    );
  };
  const fbOn = plan.flashback === "approve" || (recipe?.flashbackOn && plan.flashback !== "drop");

  const inspector: Record<Tool, React.ReactNode> = {
    trim: <>
      <h4>Trim</h4><p className="z-mut z-sm">Start and end of the clip. The hook must land in the first 3 s.</p>
      <div className="z-kv"><span>Start</span><b className="z-mono">{fmt(plan.trim_in)}</b></div>
      <div className="z-kv"><span>End</span><b className="z-mono">{fmt(plan.trim_out)}</b></div>
      <div className="z-kv"><span>Length</span><b className="z-mono">{len.toFixed(1)} s</b></div>
      <button type="button" className="z-btn z-full" disabled={!editable || hs == null} title={hs == null ? "The judge gave no hook time for this clip" : undefined}
        onClick={() => hs != null && change({ trim_in: clampTrim(Math.max(0, hs), plan.trim_out, total)[0] })}>Snap start to hook{hs != null ? ` (${mmss(hs)})` : ""}</button>
    </>,
    cap: <>
      <h4>Captions</h4><p className="z-mut z-sm">Word captions are the D073 A/B variant. Emphasis words get the highlight.</p>
      <div className="z-seg" role="group" aria-label="Caption style">
        <button type="button" className={plan.caption_style === "words" ? "z-on" : ""} disabled={!editable} onClick={() => change({ caption_style: "words" })}>Word pop</button>
        <button type="button" className={plan.caption_style === "line" ? "z-on" : ""} disabled={!editable} onClick={() => change({ caption_style: "line" })}>Full line</button>
      </div>
      <label className="z-lbl" htmlFor="e-cw">Emphasis words</label>
      <input id="e-cw" className="z-fld" value={capText} maxLength={60} disabled={!editable}
        onChange={(e) => { const v = e.target.value.toUpperCase(); setCapText(v); setPlan((p) => ({ ...p, emphasis_words: emphasisWords(v) })); }}
        onBlur={() => setHist((h) => [...h.slice(-30), plan])} />
    </>,
    head: <>
      <h4>Headline</h4><p className="z-mut z-sm">Headline box on every clip, at least 60 px (D114).</p>
      <label className="z-lbl" htmlFor="e-h">Text</label>
      <textarea id="e-h" className="z-fld" rows={3} maxLength={90} value={plan.headline} disabled={!editable}
        onChange={(e) => setPlan((p) => ({ ...p, headline: e.target.value.toUpperCase() }))} onBlur={() => setHist((h) => [...h.slice(-30), plan])} />
      {clip.title && clip.title.toUpperCase() !== plan.headline && (
        <div className="z-kv"><span>Clip title</span><b style={{ cursor: editable ? "pointer" : undefined }} onClick={() => editable && change({ headline: clip.title!.toUpperCase() })}>{clip.title}</b></div>
      )}
    </>,
    crop: <>
      <h4>Crop</h4><p className="z-mut z-sm">Where the 9:16 window sits on the stream. Drag the box.</p>
      {source ? (
        <div ref={srcBox} className="z-src">
          <video src={source} muted playsInline preload="metadata" />
          <div className="z-cropbox" role="slider" tabIndex={0} aria-label="Crop position" aria-valuemin={0} aria-valuemax={100}
            aria-valuenow={Math.round(plan.crop_x * 100)} style={{ left: `${(plan.crop_x - CROP_W / 2) * 100}%` }} onPointerDown={dragCrop}
            onKeyDown={(e) => { if (!editable) return; if (e.key === "ArrowLeft" || e.key === "ArrowRight") change({ crop_x: +Math.max(CROP_W / 2, Math.min(1 - CROP_W / 2, plan.crop_x + (e.key === "ArrowLeft" ? -0.02 : 0.02))).toFixed(3) }); }} />
        </div>
      ) : <div className="z-empty"><div><b>No stream copy</b>This clip has no 16:9 source saved, so the crop cannot move.</div></div>}
      <div className="z-kv"><span>Centre</span><b className="z-mono">{Math.round(plan.crop_x * 100)}%</b></div>
    </>,
    fb: <>
      <h4>Flashback</h4><p className="z-mut z-sm">Hard cut back to a related moment with heavy effects and a rewind sound (D113). Never automatic.</p>
      {recipe?.proposal ? <>
        <div className="z-fbpick z-on" style={{ cursor: "default" }}><span><b>{recipe.proposal.source_moment || "Proposed moment"}</b><small>{recipe.proposal.reason}</small></span></div>
        <div className="z-seg" role="group" aria-label="Flashback decision">
          <button type="button" className={fbOn ? "z-on" : ""} disabled={!editable} onClick={() => change({ flashback: "approve" })}>Use it</button>
          <button type="button" className={plan.flashback === "drop" ? "z-on" : ""} disabled={!editable} onClick={() => change({ flashback: "drop" })}>Drop it</button>
        </div>
        <div className="z-kv"><span>Rewind SFX</span><b>{fbOn ? "On" : "Off"}</b></div>
        <div className="z-kv"><span>Effect strength</span><b>{fbOn ? "Intense" : "—"}</b></div>
      </> : <div className="z-empty"><div><b>No flashback proposed</b>The editing agent proposes one with a reason and source moment when it fits.</div></div>}
    </>,
    aud: <>
      <h4>Audio</h4><p className="z-mut z-sm">Music and sound effects from the clip&apos;s edit recipe. Take any off.</p>
      {audioTools.length ? <div className="z-tools">{audioTools.map(toolBtn)}</div> : <p className="z-note">No music or SFX on this clip.</p>}
      {otherTools.length > 0 && <><span className="z-lbl">Other effects</span><div className="z-tools">{otherTools.map(toolBtn)}</div></>}
      {typeof clip.qa?.lufs === "number" && <div className="z-kv"><span>Loudness</span><b className="z-mono">{clip.qa.lufs} LUFS</b></div>}
      {!recipe && <p className="z-note">This clip was rendered before edit recipes (D114).</p>}
    </>,
  };

  return (
    <div className="z-id-editor">
      <div className="z-edbar">
        <button type="button" className="z-btn" onClick={() => ui.closeEditor(null)}><Ico n="back" size={15} />Back</button>
        <div className="z-edttl"><span className="z-lbl">Editing · {who}</span><b>{clip.title ?? clip.job_id}</b></div>
        <span className="z-sp" />
        <span className={`z-mut z-sm${dirty ? " z-dirty" : ""}`}>{!editable ? (canReview(clip) ? "Only clips waiting for review can be edited" : "Only this pod's owner can edit") : dirty ? editNote(plan, base).replace("Editor: ", "Unsaved: ") : "No changes yet"}</span>
        {hist.length > 0 && <button type="button" className="z-btn" onClick={undo} title="Ctrl+Z">Undo</button>}
        <button type="button" className="z-btn" onClick={() => ui.closeEditor(null)}>Cancel</button>
        <button type="button" className="z-btn z-w" disabled={busy || (dirty && !editable)} onClick={() => void save()}>{busy ? "Saving…" : "Save changes"}</button>
      </div>
      <div className="z-edmain">
        <nav className="z-edtools" aria-label="Editing tools">
          {TOOLS.map(([k, l, ic]) => (
            <button key={k} type="button" className={tool === k ? "z-on" : ""} aria-pressed={tool === k} onClick={() => setTool(k)}><Ico n={ic} size={20} sw={1.8} /><span>{l}</span></button>
          ))}
        </nav>
        <div className="z-edstage">
          <div className="z-edphone">
            {src ? <video ref={vid} src={src} poster={poster ?? undefined} playsInline loop autoPlay muted /> : <div className="z-empty" style={{ height: "100%" }}>Loading clip…</div>}
            {plan.headline.trim() && plan.headline.trim() !== base.headline.trim() && <span className="z-edhead">{plan.headline}</span>}
            <div className="z-safe" aria-hidden="true" />
          </div>
        </div>
        <aside className="z-edinsp">{inspector[tool]}</aside>
      </div>
      <div className="z-edtl">
        <div className="z-tlhead">
          <button type="button" className="z-btn z-sm2" onClick={toggle}>{paused ? "▶ Play" : "❚❚ Pause"}</button>
          <span className="z-mono">{mmss(t)} / {mmss(total)}</span><span className="z-sp" />
          <span className="z-mut z-sm">Drag the handles to trim. Zoom effects are off for every clip.</span>
        </div>
        <div className="z-tracks">
          <div className="z-trk z-vid"><span className="z-tn">Video</span>
            <div className="z-lane z-tl-click" ref={lane} onPointerDown={seek}>
              {Array.from({ length: 14 }, (_, i) => <i key={i} style={{ backgroundImage: poster ? `url("${poster}")` : undefined }} />)}
              <div className="z-trim" style={{ left: pct(plan.trim_in), width: pct(len) }}>
                <b className="z-hd z-l" role="slider" aria-label={`Trim start ${plan.trim_in.toFixed(1)} s`} aria-valuenow={plan.trim_in} tabIndex={0} onPointerDown={dragTrim("a")}
                  onKeyDown={(e) => { if (editable && (e.key === "ArrowLeft" || e.key === "ArrowRight")) change({ trim_in: clampTrim(plan.trim_in + (e.key === "ArrowLeft" ? -0.5 : 0.5), plan.trim_out, total)[0] }); }} />
                <b className="z-hd z-r" role="slider" aria-label={`Trim end ${plan.trim_out.toFixed(1)} s`} aria-valuenow={plan.trim_out} tabIndex={0} onPointerDown={dragTrim("b")}
                  onKeyDown={(e) => { if (editable && (e.key === "ArrowLeft" || e.key === "ArrowRight")) change({ trim_out: clampTrim(plan.trim_in, plan.trim_out + (e.key === "ArrowLeft" ? -0.5 : 0.5), total)[1] }); }} />
              </div>
            </div></div>
          <div className="z-trk z-cap"><span className="z-tn">Captions</span>
            <div className="z-lane">{words.map((w, i) => <em key={`${w}${i}`} style={{ left: `calc(${pct(plan.trim_in + (len * (i + 0.5)) / Math.max(1, words.length))} - 20px)` }}>{w}</em>)}
              {words.length === 0 && <span className="z-mut z-sm" style={{ position: "absolute", left: 10, top: 6 }}>No emphasis words</span>}</div></div>
          <div className="z-trk z-aud"><span className="z-tn">Audio</span>
            {wave ? <div className="z-lane z-wave">{wave.map((h, i) => <i key={i} style={{ height: `${Math.max(6, Math.min(100, h))}%` }} />)}</div>
              : <div className="z-lane z-wave z-none">no waveform measured for this render</div>}</div>
          <div className="z-ph" style={{ left: `calc(84px + (100% - 84px) * ${t / total})` }} />
        </div>
      </div>
    </div>
  );
}
