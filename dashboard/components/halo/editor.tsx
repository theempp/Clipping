"use client";
// Edit clip (D116): takes over the main area, bars stay. Tools: Trim, Cut, Captions, Headline, Crop, Flashback, Audio.
// No zoom tool (D112). Save sends only what changed as a revision (kind "trim", payload.edit), which the PC
// re-renders and the learn loop reads as a manual edit (D114). Every control maps to a field the worker
// reads (worker/src/clipworker/editplan.py). Anything else goes to the agent as a plain-English revision. Nothing here posts.
import { useEffect, useMemo, useRef, useState } from "react";
import {
  TOOL_LABEL, clipRecipe, droppedStarts, editNote, editPayload, keptLength, pieces, removeSplit, retrim, splitAt, toggleDrop,
} from "@/lib/logic";
import { useStore } from "@/lib/store";
import type { Clip, EditPlan } from "@/lib/types";
import { basePlan } from "@/lib/halo";
import { useReview } from "./review";
import { fmtT, hookRange, useVideoCtl } from "./scrub";
import { Ico, useMedia } from "./ui";

type Tool = "trim" | "cut" | "cap" | "head" | "crop" | "fb" | "aud";
const TOOLS: [Tool, string, string][] = [["trim", "Trim", "trim"], ["cut", "Cut", "split"], ["cap", "Captions", "cap"], ["head", "Headline", "head"],
  ["crop", "Crop", "crop"], ["fb", "Flashback", "fb"], ["aud", "Audio", "aud"]];
const CROP_W = 0.316; // a 9:16 window is 31.6% of a 16:9 frame
const AUDIO_TOOLS = ["music_cue", "sfx_whoosh", "sfx_hit", "sfx_glitch"];
const FRAME = 1 / 30;
const KEYS: [string, string][] = [["Space", "Play / pause"], ["← →", "Back / forward 1 s (Shift: 5 s)"], [", .", "One frame back / forward"],
  ["I / O", "Set start / end at the playhead"], ["S", "Split at the playhead"], ["Del", "Delete or restore the selected piece"],
  ["Ctrl+Z", "Undo"], ["Ctrl+Shift+Z", "Redo"], ["?", "Show these keys"]];

const sameWords = (a: string[], b: string[]) => a.join(" ") === b.join(" ");
const FILLER = new Set("the and you all for are but not his her him she was has had get gets got with that this from they them before after about into out just what when then than its it's our your their who how why can will".split(" "));
const cleanWord = (w: string) => w.replace(/^[.,!?"']+|[.,!?"']+$/g, "").toLowerCase();

export function Editor({ clip }: { clip: Clip }) {
  const { sendEdit, canReview, snap } = useStore();
  const ui = useReview();
  const base = useMemo(() => basePlan(clip), [clip.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const [plan, setPlan] = useState<EditPlan>(() => ({ ...base, headline: ui.draft(clip) || base.headline }));
  const [hist, setHist] = useState<EditPlan[]>([]);
  const [fut, setFut] = useState<EditPlan[]>([]);
  const [tool, setTool] = useState<Tool>("trim");
  const [sel, setSel] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [keys, setKeys] = useState(false);
  const [word, setWord] = useState("");
  const src = useMedia(clip.storage_path);
  const poster = useMedia(clip.thumb_path);
  const source = useMedia(clip.source_path ?? null);
  const vid = useRef<HTMLVideoElement>(null);
  const ctl = useVideoCtl(vid, src, false);
  const lane = useRef<HTMLDivElement>(null);
  const srcBox = useRef<HTMLDivElement>(null);
  const total = Math.max(1, clip.duration_s ?? 30);
  const recipe = clipRecipe(clip);
  const editable = clip.state === "pending_review" && canReview(clip);
  const changes = editPayload(plan, base);
  const dirty = Object.keys(changes).length > 0;
  const who = snap.streamers.find((s) => s.id === clip.streamer_id)?.display_name ?? clip.channel_key.split(":")[1];
  const t = ctl.t;
  const hook = hookRange(clip.judge?.hook_window);
  const parts = pieces(plan);
  const dropped = droppedStarts(plan);
  const kept = keptLength(plan);

  /** One undoable step. */
  const commit = (next: EditPlan) => { if (next === plan) return; setHist((h) => [...h.slice(-40), plan]); setFut([]); setPlan(next); };
  const change = (p: Partial<EditPlan>) => commit({ ...plan, ...p });
  /** End of a drag or a typing run: record `before` as the undo point. */
  const settle = (before: EditPlan) => { setHist((h) => [...h.slice(-40), before]); setFut([]); };
  const undo = () => { if (!hist.length) return; setFut((f) => [plan, ...f]); setPlan(hist[hist.length - 1]); setHist((h) => h.slice(0, -1)); };
  const redo = () => { if (!fut.length) return; setHist((h) => [...h, plan]); setPlan(fut[0]); setFut((f) => f.slice(1)); };
  const reset = () => commit({ ...base });

  const seek = (s: number) => ctl.seek(Math.max(0, Math.min(total, s)));
  const pieceAt = (s: number) => parts.find(([a, b]) => s >= a && s < b)?.[0] ?? null;
  const split = () => {
    if (!editable) return;
    const n = splitAt(plan, t);
    if (!n) { ui.toast("Move the playhead inside the clip, away from the ends and other splits."); return; }
    commit(n); setTool("cut"); setSel(+t.toFixed(2));
  };
  const dropSel = () => {
    if (!editable) return;
    const s = sel ?? pieceAt(t);
    if (s == null) return;
    if (parts.length < 2) { ui.toast("Split the clip first (S), then delete the piece you don't want."); setTool("cut"); return; }
    const n = toggleDrop(plan, s);
    if (n === plan) { ui.toast("At least one piece has to stay."); return; }
    commit(n); setSel(s);
  };
  const setIn = () => editable && commit(retrim(plan, t, plan.trim_out, total));
  const setOut = () => editable && commit(retrim(plan, plan.trim_in, t, total));

  // Playback stays inside the trim and jumps over deleted pieces.
  const live = useRef(plan);
  live.current = plan;
  useEffect(() => {
    const v = vid.current;
    if (!v) return;
    let raf = 0;
    const tick = () => {
      const p = live.current;
      if (!v.paused) {
        const cut = pieces(p).find(([a, b]) => droppedStarts(p).includes(a) && v.currentTime >= a && v.currentTime < b - 0.02);
        if (cut) v.currentTime = cut[1];
        else if (v.currentTime >= p.trim_out - 0.02 || v.currentTime < p.trim_in - 0.05) {
          const first = pieces(p).find(([a]) => !droppedStarts(p).includes(a));
          v.currentTime = first ? first[0] : p.trim_in;
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [src]);

  useEffect(() => { if (sel != null && !parts.some(([a]) => a === sel)) setSel(null); }, [parts, sel]);

  // Shortcuts (re-bound every render so they see the current plan).
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el.closest("input,textarea,select,[contenteditable]") || document.querySelector(".z-pop")) return;
      const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      const mod = e.ctrlKey || e.metaKey;
      const big = e.shiftKey ? 5 : 1;
      if (mod && k === "z") { e.preventDefault(); if (e.shiftKey) redo(); else undo(); return; }
      if (mod && k === "y") { e.preventDefault(); redo(); return; }
      if (mod || e.altKey) return;
      if (el.closest("button,[role=slider]") && (k === " " || k === "Enter" || k === "ArrowLeft" || k === "ArrowRight")) return;
      const map: Record<string, () => void> = {
        " ": ctl.toggle, k: ctl.toggle, ArrowLeft: () => seek(t - big), ArrowRight: () => seek(t + big), j: () => seek(t - big), l: () => seek(t + big),
        ",": () => ctl.step(-FRAME), ".": () => ctl.step(FRAME), i: setIn, o: setOut, s: split, Delete: dropSel, Backspace: dropSel,
        "?": () => setKeys((x) => !x), m: () => ctl.setMuted(!ctl.muted), Home: () => seek(plan.trim_in), End: () => seek(plan.trim_out - 0.1),
      };
      const f = map[k];
      if (f) { e.preventDefault(); f(); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  const frac = (el: HTMLElement | null, x: number) => { const r = el?.getBoundingClientRect(); return r ? Math.max(0, Math.min(1, (x - r.left) / r.width)) : 0; };
  const dragTrim = (kind: "a" | "b") => (e: React.PointerEvent) => {
    if (!editable) return;
    e.preventDefault(); e.stopPropagation();
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    const before = plan;
    let last = plan;
    ctl.grab();
    const move = (ev: PointerEvent) => {
      const s = frac(lane.current, ev.clientX) * total;
      last = kind === "a" ? retrim(before, s, before.trim_out, total) : retrim(before, before.trim_in, s, total);
      setPlan(last);
      if (vid.current) vid.current.currentTime = kind === "a" ? last.trim_in : Math.max(last.trim_in, last.trim_out - 0.5);
    };
    const up = () => {
      el.removeEventListener("pointermove", move); el.removeEventListener("pointerup", up); el.removeEventListener("pointercancel", up);
      if (last.trim_in !== before.trim_in || last.trim_out !== before.trim_out) settle(before);
    };
    el.addEventListener("pointermove", move); el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
  };
  /** Click picks the piece; drag scrubs. */
  const scrub = (pick: boolean) => (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    ctl.grab();
    const s0 = frac(lane.current, e.clientX) * total;
    seek(s0);
    if (pick) setSel(pieceAt(s0));
    const move = (ev: PointerEvent) => seek(frac(lane.current, ev.clientX) * total);
    const up = () => { el.removeEventListener("pointermove", move); el.removeEventListener("pointerup", up); el.removeEventListener("pointercancel", up); ctl.release(); };
    el.addEventListener("pointermove", move); el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
  };
  const dragCrop = (e: React.PointerEvent) => {
    if (!editable) return;
    e.preventDefault();
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    const before = plan, r = srcBox.current?.getBoundingClientRect(), start = e.clientX, from = plan.crop_x;
    let last = from;
    const move = (ev: PointerEvent) => { if (!r) return; last = Math.max(CROP_W / 2, Math.min(1 - CROP_W / 2, from + (ev.clientX - start) / r.width)); setPlan((p) => ({ ...p, crop_x: +last.toFixed(3) })); };
    const up = () => { el.removeEventListener("pointermove", move); el.removeEventListener("pointerup", up); el.removeEventListener("pointercancel", up); if (last !== from) settle(before); };
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
  const askAgent = () => {
    if (dirty) { ui.toast("Save or reset your edits first, then ask the agent."); return; }
    ui.askRevise(clip.id);
  };

  const peaks = clip.manifest?.peaks;
  const wave = Array.isArray(peaks) && peaks.length > 8 && peaks.every((v) => typeof v === "number") ? (peaks as number[]) : null;
  const len = plan.trim_out - plan.trim_in;
  const pct = (s: number) => `${(s / total) * 100}%`;
  const audioTools = (recipe?.tools ?? []).filter((x) => AUDIO_TOOLS.includes(x));
  const otherTools = (recipe?.tools ?? []).filter((x) => !AUDIO_TOOLS.includes(x));
  const fbOn = plan.flashback === "approve" || (recipe?.flashbackOn && plan.flashback !== "drop");
  const touched: Record<Tool, boolean> = {
    trim: "trim_in" in changes, cut: "cuts" in changes || plan.splits.length > 0, cap: "caption_style" in changes || "emphasis_words" in changes,
    head: "headline" in changes, crop: "crop_x" in changes, fb: "flashback" in changes, aud: "remove_tools" in changes,
  };
  const ticks = useMemo(() => { const step = total > 90 ? 15 : total > 40 ? 5 : total > 15 ? 2 : 1; return Array.from({ length: Math.floor(total / step) + 1 }, (_, i) => i * step); }, [total]);
  const thumbs = useMemo(() => Array.from({ length: 14 }, (_, i) => <i key={i} style={{ backgroundImage: poster ? `url("${poster}")` : undefined }} />), [poster]);
  const waveEl = useMemo(() => (wave ? wave.map((h, i) => <i key={i} style={{ height: `${Math.max(6, Math.min(100, h))}%` }} />) : null), [wave]);
  const suggest = useMemo(() => {
    const from = [clip.title, clip.hook, plan.headline].filter(Boolean).join(" ");
    return [...new Set(from.split(/\s+/).map(cleanWord).filter((w) => w.length > 2 && !FILLER.has(w) && !plan.emphasis_words.includes(w)))].slice(0, 10);
  }, [clip.title, clip.hook, plan.headline, plan.emphasis_words]);
  const addWord = (w: string) => {
    const c = cleanWord(w);
    if (!c || plan.emphasis_words.includes(c) || plan.emphasis_words.length >= 12) return;
    change({ emphasis_words: [...plan.emphasis_words, c] });
  };
  const nudge = (which: "in" | "out", d: number) => commit(which === "in" ? retrim(plan, plan.trim_in + d, plan.trim_out, total) : retrim(plan, plan.trim_in, plan.trim_out + d, total));
  const toolBtn = (x: string) => {
    const off = (plan.remove_tools ?? []).includes(x);
    return (
      <button key={x} type="button" className={`z-tog${off ? "" : " z-on"}`} aria-pressed={!off} disabled={!editable}
        onClick={() => change({ remove_tools: off ? (plan.remove_tools ?? []).filter((y) => y !== x) : [...(plan.remove_tools ?? []), x] })}>
        <span className="z-tdot" />{TOOL_LABEL[x] ?? x}<small>{off ? "Off" : "On"}</small></button>
    );
  };
  const headOpts = [...new Set([clip.title, clip.hook, base.headline].filter((x): x is string => !!x && !!x.trim()).map((x) => x.toUpperCase()))]
    .filter((x) => x !== plan.headline.trim());

  const inspector: Record<Tool, React.ReactNode> = {
    trim: <>
      <h4>Trim</h4><p className="z-mut z-sm">Pick where the clip starts and ends. Drag the blue handles on the timeline, or park the playhead and press <kbd>I</kbd> / <kbd>O</kbd>. The hook should land in the first 3 s.</p>
      {(["in", "out"] as const).map((w) => (
        <div key={w} className="z-trow">
          <span>{w === "in" ? "Start" : "End"}</span>
          <button type="button" className="z-ib" disabled={!editable} aria-label={`${w === "in" ? "Start" : "End"} 0.1 s earlier`} onClick={() => nudge(w, -0.1)}>−</button>
          <b className="z-mono">{fmtT(w === "in" ? plan.trim_in : plan.trim_out)}</b>
          <button type="button" className="z-ib" disabled={!editable} aria-label={`${w === "in" ? "Start" : "End"} 0.1 s later`} onClick={() => nudge(w, 0.1)}>+</button>
          <button type="button" className="z-btn z-sm2" disabled={!editable} onClick={w === "in" ? setIn : setOut}>{w === "in" ? "Start here" : "End here"} <kbd>{w === "in" ? "I" : "O"}</kbd></button>
        </div>
      ))}
      <div className="z-kv"><span>Trimmed length</span><b className="z-mono">{len.toFixed(1)} s</b></div>
      {dropped.length > 0 && <div className="z-kv"><span>After cuts</span><b className="z-mono">{kept.toFixed(1)} s</b></div>}
      <button type="button" className="z-btn z-full" disabled={!editable || !hook} title={!hook ? "The judge gave no hook time for this clip" : undefined}
        onClick={() => hook && commit(retrim(plan, hook[0], plan.trim_out, total))}>Start at the hook{hook ? ` (${fmtT(hook[0])})` : ""}</button>
      {"trim_in" in changes && <button type="button" className="z-btn z-full" disabled={!editable} onClick={() => commit(retrim(plan, base.trim_in, base.trim_out, total))}>Reset trim</button>}
    </>,
    cut: <>
      <h4>Cut out the middle</h4><p className="z-mut z-sm">1. Move the playhead to where a dead bit starts and <b>Split</b>. 2. Split again where it ends. 3. Click that piece and <b>Delete</b> it. The PC removes it on re-render.</p>
      <div className="z-acts z-tight">
        <button type="button" className="z-btn z-w" disabled={!editable} onClick={split}><Ico n="split" size={15} />Split at {fmtT(t)} <kbd>S</kbd></button>
      </div>
      <span className="z-lbl">Pieces · {parts.length}</span>
      <ul className="z-pieces">
        {parts.map(([a, b], i) => {
          const off = dropped.includes(a);
          return (
            <li key={a} className={`${off ? "z-off" : ""}${sel === a ? " z-sel" : ""}`}>
              <button type="button" className="z-pc" onClick={() => { setSel(a); seek(a); }}>
                <span className="z-pn">{i + 1}</span><span className="z-mono">{fmtT(a)} – {fmtT(b)}</span><small>{(b - a).toFixed(1)} s{off ? " · deleted" : ""}</small>
              </button>
              <button type="button" className="z-ib" disabled={!editable || parts.length < 2} aria-label={off ? "Restore piece" : "Delete piece"} title={off ? "Restore" : "Delete"}
                onClick={() => { const n = toggleDrop(plan, a); if (n === plan) ui.toast("At least one piece has to stay."); else commit(n); }}><Ico n={off ? "restore" : "trash"} size={14} /></button>
              {i > 0 && <button type="button" className="z-ib" disabled={!editable} aria-label={`Join with piece ${i}`} title="Remove the split before this piece" onClick={() => commit(removeSplit(plan, a))}><Ico n="x" size={12} /></button>}
            </li>
          );
        })}
      </ul>
      {parts.length < 2 && <p className="z-note">No splits yet. The whole trimmed clip is one piece.</p>}
      {plan.splits.length > 0 && <button type="button" className="z-btn z-full" disabled={!editable} onClick={() => commit({ ...plan, splits: [], drop: [] })}>Remove all splits</button>}
    </>,
    cap: <>
      <h4>Captions</h4><p className="z-mut z-sm">How captions break up, and which words get the highlight. Word pop is the D073 A/B variant.</p>
      <div className="z-seg" role="group" aria-label="Caption style">
        <button type="button" className={plan.caption_style === "words" ? "z-on" : ""} disabled={!editable} onClick={() => change({ caption_style: "words" })}>Word pop · 3</button>
        <button type="button" className={plan.caption_style === "line" ? "z-on" : ""} disabled={!editable} onClick={() => change({ caption_style: "line" })}>Full line · 7</button>
      </div>
      <span className="z-lbl">Highlighted words · {plan.emphasis_words.length}/12</span>
      <div className="z-wchips">
        {plan.emphasis_words.map((w) => (
          <span key={w} className="z-wchip">{w.toUpperCase()}
            <button type="button" disabled={!editable} aria-label={`Remove ${w}`} onClick={() => change({ emphasis_words: plan.emphasis_words.filter((x) => x !== w) })}><Ico n="x" size={10} sw={3} /></button></span>
        ))}
        {plan.emphasis_words.length === 0 && <span className="z-mut z-sm">None yet. Add one below.</span>}
      </div>
      <form className="z-addw" onSubmit={(e) => { e.preventDefault(); word.split(/[\s,]+/).forEach(addWord); setWord(""); }}>
        <input className="z-fld" value={word} maxLength={40} disabled={!editable || plan.emphasis_words.length >= 12} placeholder="Type a word, press Enter" onChange={(e) => setWord(e.target.value)} />
        <button type="submit" className="z-btn" disabled={!editable || !word.trim()}><Ico n="plus" size={14} />Add</button>
      </form>
      {suggest.length > 0 && <><span className="z-lbl">Suggested from the title</span>
        <div className="z-chipx">{suggest.map((w) => <button type="button" key={w} disabled={!editable} onClick={() => addWord(w)}>+ {w}</button>)}</div></>}
      {!sameWords(plan.emphasis_words, base.emphasis_words) && <button type="button" className="z-btn z-full" disabled={!editable} onClick={() => change({ emphasis_words: base.emphasis_words })}>Back to the original words</button>}
    </>,
    head: <>
      <h4>Headline</h4><p className="z-mut z-sm">The box burned in at the top of every clip, at least 60 px (D114).</p>
      <label className="z-lbl" htmlFor="e-h">Text <span className="z-mono">{plan.headline.length}/90</span></label>
      <HeadBox value={plan.headline} disabled={!editable} onLive={(v) => setPlan((p) => ({ ...p, headline: v }))} onDone={settle} plan={plan} />
      {headOpts.length > 0 && <><span className="z-lbl">Use instead</span>
        <div className="z-opts">{headOpts.map((h) => <button type="button" key={h} disabled={!editable} onClick={() => change({ headline: h })}>{h}</button>)}</div></>}
    </>,
    crop: <>
      <h4>Crop</h4><p className="z-mut z-sm">Where the 9:16 window sits on the 16:9 stream. Drag the box, use the arrow keys on it, or pick a spot.</p>
      {source ? (
        <div ref={srcBox} className="z-src">
          <video src={source} muted playsInline preload="metadata" />
          <div className="z-cropbox" role="slider" tabIndex={0} aria-label="Crop position" aria-valuemin={0} aria-valuemax={100}
            aria-valuenow={Math.round(plan.crop_x * 100)} style={{ left: `${(plan.crop_x - CROP_W / 2) * 100}%` }} onPointerDown={dragCrop}
            onKeyDown={(e) => { if (!editable) return; if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); change({ crop_x: +Math.max(CROP_W / 2, Math.min(1 - CROP_W / 2, plan.crop_x + (e.key === "ArrowLeft" ? -0.02 : 0.02))).toFixed(3) }); } }} />
        </div>
      ) : <div className="z-empty"><div><b>No stream copy</b>This clip has no 16:9 source saved, so the crop cannot move.</div></div>}
      <div className="z-seg" role="group" aria-label="Crop presets">
        {([["Left", CROP_W / 2], ["Centre", 0.5], ["Right", 1 - CROP_W / 2]] as const).map(([l, x]) => (
          <button key={l} type="button" className={Math.abs(plan.crop_x - x) < 0.01 ? "z-on" : ""} disabled={!editable || !source} onClick={() => change({ crop_x: +x.toFixed(3) })}>{l}</button>))}
      </div>
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
      </> : <div className="z-empty"><div><b>No flashback proposed</b>The editing agent proposes one with a reason and source moment when it fits. Want one anyway? Use <b>Ask the agent</b>.</div></div>}
    </>,
    aud: <>
      <h4>Audio &amp; effects</h4><p className="z-mut z-sm">Music, sound effects and effects from the clip&apos;s edit recipe. Click one to take it off or put it back.</p>
      {audioTools.length ? <div className="z-tools">{audioTools.map(toolBtn)}</div> : <p className="z-note">No music or SFX on this clip.</p>}
      {otherTools.length > 0 && <><span className="z-lbl">Other effects</span><div className="z-tools">{otherTools.map(toolBtn)}</div></>}
      {typeof clip.qa?.lufs === "number" && <div className="z-kv"><span>Loudness</span><b className="z-mono">{clip.qa.lufs} LUFS</b></div>}
      {!recipe && <p className="z-note">This clip was rendered before edit recipes (D114).</p>}
      <p className="z-note">To add music or an effect that isn&apos;t listed, use <b>Ask the agent</b> and say what you want.</p>
    </>,
  };

  return (
    <div className="z-id-editor">
      <div className="z-edbar">
        <button type="button" className="z-btn" onClick={() => ui.closeEditor(null)}><Ico n="back" size={15} />Back</button>
        <div className="z-edttl"><span className="z-lbl">Editing · {who}</span><b>{clip.title ?? clip.job_id}</b></div>
        <span className="z-sp" />
        <span className={`z-mut z-sm z-edsum${dirty ? " z-dirty" : ""}`} title={dirty ? editNote(plan, base) : undefined}>
          {!editable ? (canReview(clip) ? "Only clips waiting for review can be edited" : "Only this pod's owner can edit") : dirty ? editNote(plan, base).replace("Editor: ", "Unsaved: ") : "No changes yet"}</span>
        <div className="z-ibg">
          <button type="button" className="z-ib" disabled={!hist.length} onClick={undo} aria-label="Undo" title="Undo (Ctrl+Z)"><Ico n="undo" size={15} /></button>
          <button type="button" className="z-ib" disabled={!fut.length} onClick={redo} aria-label="Redo" title="Redo (Ctrl+Shift+Z)"><Ico n="redo" size={15} /></button>
          <button type="button" className="z-ib" disabled={!dirty || !editable} onClick={reset} aria-label="Reset all edits" title="Reset all edits"><Ico n="restore" size={15} /></button>
          <button type="button" className={`z-ib${keys ? " z-on" : ""}`} onClick={() => setKeys((x) => !x)} aria-label="Keyboard shortcuts" title="Keyboard shortcuts (?)"><Ico n="key" size={15} /></button>
        </div>
        <button type="button" className="z-btn" disabled={!editable} onClick={askAgent} title="Describe any other change in plain English"><Ico n="chat" size={15} />Ask the agent</button>
        <button type="button" className="z-btn" onClick={() => ui.closeEditor(null)}>Cancel</button>
        <button type="button" className="z-btn z-w" disabled={busy || (dirty && !editable)} onClick={() => void save()}>{busy ? "Saving…" : "Save changes"}</button>
      </div>
      <div className="z-edmain">
        <nav className="z-edtools" aria-label="Editing tools">
          {TOOLS.map(([k, l, ic]) => (
            <button key={k} type="button" className={tool === k ? "z-on" : ""} aria-pressed={tool === k} onClick={() => setTool(k)}>
              <Ico n={ic} size={20} sw={1.8} /><span>{l}</span>{touched[k] && <i className="z-tchg" aria-label="changed" />}</button>
          ))}
        </nav>
        <div className="z-edstage">
          <div className="z-edphone">
            {src ? <video ref={vid} src={src} poster={poster ?? undefined} playsInline loop autoPlay muted={ctl.muted} onClick={ctl.toggle} /> : <div className="z-empty" style={{ height: "100%" }}>Loading clip…</div>}
            {plan.headline.trim() && plan.headline.trim() !== base.headline.trim() && <span className="z-edhead">{plan.headline}</span>}
            <div className="z-safe" aria-hidden="true" />
            {src && ctl.paused && <button type="button" className="z-bigplay" aria-label="Play" onClick={ctl.toggle}><Ico n="play" size={26} sw={2.2} /></button>}
          </div>
          {dropped.length > 0 && <span className="z-edbadge">Preview skips {dropped.length} deleted piece{dropped.length === 1 ? "" : "s"}</span>}
          {keys && (
            <div className="z-keys" role="dialog" aria-label="Keyboard shortcuts">
              <b>Shortcuts</b>
              {KEYS.map(([k, d]) => <div key={k}><kbd>{k}</kbd><span>{d}</span></div>)}
            </div>
          )}
        </div>
        <aside className="z-edinsp">{inspector[tool]}</aside>
      </div>
      <div className="z-edtl">
        <div className="z-tlhead">
          <div className="z-ibg">
            <button type="button" className="z-ib" aria-label="Back one frame" title="Back one frame ( , )" onClick={() => ctl.step(-FRAME)}><Ico n="stepb" size={14} /></button>
            <button type="button" className="z-ib z-splay" aria-label={ctl.paused ? "Play" : "Pause"} title="Play / pause (Space)" onClick={ctl.toggle}><Ico n={ctl.paused ? "play" : "pause"} size={15} sw={2.4} /></button>
            <button type="button" className="z-ib" aria-label="Forward one frame" title="Forward one frame ( . )" onClick={() => ctl.step(FRAME)}><Ico n="stepf" size={14} /></button>
          </div>
          <span className="z-mono z-tlt">{fmtT(t)} <i>/ {fmtT(total)}</i></span>
          <button type="button" className="z-ib z-txt" onClick={ctl.cycleRate} title="Playback speed">{ctl.rate}x</button>
          <button type="button" className="z-ib" onClick={() => ctl.setMuted(!ctl.muted)} aria-label={ctl.muted ? "Sound on" : "Sound off"} title="Sound (M)"><Ico n={ctl.muted ? "mute" : "vol"} size={15} /></button>
          <span className="z-tldiv" />
          <button type="button" className="z-btn z-sm2" disabled={!editable} onClick={setIn} title="Set start at the playhead (I)">[ Start here</button>
          <button type="button" className="z-btn z-sm2" disabled={!editable} onClick={setOut} title="Set end at the playhead (O)">End here ]</button>
          <button type="button" className="z-btn z-sm2" disabled={!editable} onClick={split} title="Split at the playhead (S)"><Ico n="split" size={13} />Split</button>
          <button type="button" className="z-btn z-sm2" disabled={!editable || parts.length < 2} onClick={dropSel} title="Delete or restore the selected piece (Del)">
            <Ico n={sel != null && dropped.includes(sel) ? "restore" : "trash"} size={13} />{sel != null && dropped.includes(sel) ? "Restore" : "Delete piece"}</button>
          <span className="z-sp" />
          <span className="z-mut z-sm">{dirty ? `Final length ${kept.toFixed(1)} s` : "Drag the ruler to scrub · drag the blue handles to trim"}</span>
        </div>
        <div className="z-tracks">
          <div className="z-trk z-rul"><span className="z-tn">Time</span>
            <div className="z-lane z-ruler" onPointerDown={scrub(false)}>
              {ticks.map((s) => <span key={s} style={{ left: pct(s) }}>{Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")}</span>)}
              {hook && <i className="z-rhook" style={{ left: pct(hook[0]), width: pct(Math.max(0.3, hook[1] - hook[0])) }} title="Hook window" />}
            </div></div>
          <div className="z-trk z-vid"><span className="z-tn">Video</span>
            <div className="z-lane z-tl-click" ref={lane} onPointerDown={scrub(true)}>
              {thumbs}
              {parts.map(([a, b]) => (
                <span key={a} className={`z-piece${dropped.includes(a) ? " z-off" : ""}${sel === a ? " z-sel" : ""}`} style={{ left: pct(a), width: pct(b - a) }} />
              ))}
              {plan.splits.filter((s) => s > plan.trim_in && s < plan.trim_out).map((s) => <span key={s} className="z-splitm" style={{ left: pct(s) }} />)}
              <div className="z-trim" style={{ left: pct(plan.trim_in), width: pct(len) }}>
                <b className="z-hd z-l" role="slider" aria-label={`Trim start ${plan.trim_in.toFixed(1)} s`} aria-valuenow={plan.trim_in} tabIndex={0} onPointerDown={dragTrim("a")}
                  onKeyDown={(e) => { if (editable && (e.key === "ArrowLeft" || e.key === "ArrowRight")) { e.preventDefault(); nudge("in", e.key === "ArrowLeft" ? -0.5 : 0.5); } }} />
                <b className="z-hd z-r" role="slider" aria-label={`Trim end ${plan.trim_out.toFixed(1)} s`} aria-valuenow={plan.trim_out} tabIndex={0} onPointerDown={dragTrim("b")}
                  onKeyDown={(e) => { if (editable && (e.key === "ArrowLeft" || e.key === "ArrowRight")) { e.preventDefault(); nudge("out", e.key === "ArrowLeft" ? -0.5 : 0.5); } }} />
              </div>
            </div></div>
          <div className="z-trk z-cap"><span className="z-tn">Highlights</span>
            <div className="z-lane z-tl-click" onClick={() => setTool("cap")}>{plan.emphasis_words.map((w, i) => <em key={`${w}${i}`} style={{ left: `calc(${pct(plan.trim_in + (len * (i + 0.5)) / Math.max(1, plan.emphasis_words.length))} - 20px)` }}>{w.toUpperCase()}</em>)}
              {plan.emphasis_words.length === 0 && <span className="z-mut z-sm" style={{ position: "absolute", left: 10, top: 6 }}>No highlighted words · click to add</span>}</div></div>
          <div className="z-trk z-aud"><span className="z-tn">Audio</span>
            {waveEl ? <div className="z-lane z-wave">{waveEl}</div>
              : <div className="z-lane z-wave z-none">no waveform measured for this render</div>}</div>
          <div className="z-ph" style={{ left: `calc(84px + (100% - 84px) * ${Math.min(1, t / total)})` }} />
        </div>
      </div>
    </div>
  );
}

/** Headline textarea: types live into the plan, records one undo step when you leave it. */
function HeadBox({ value, disabled, onLive, onDone, plan }: { value: string; disabled: boolean; onLive: (v: string) => void; onDone: (before: EditPlan) => void; plan: EditPlan }) {
  const before = useRef<EditPlan | null>(null);
  return (
    <textarea id="e-h" className="z-fld" rows={3} maxLength={90} value={value} disabled={disabled}
      onFocus={() => { before.current = plan; }}
      onChange={(e) => onLive(e.target.value.toUpperCase())}
      onBlur={() => { if (before.current && before.current.headline !== value) onDone(before.current); before.current = null; }} />
  );
}
