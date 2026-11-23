"use client";
// Review state and dialogs for the Halo Pro page (D116): approve is a local step, Post asks to confirm,
// and only the confirm calls post() (review_clip approve + picked platforms). Nothing posts without both.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { cleanNote } from "@/lib/logic";
import { UNDO_MS, useNow, useStore } from "@/lib/store";
import type { Clip } from "@/lib/types";
import { PLATFORM_LABEL, type Platform, agoShort, basePlan, clipLen, clipScore, compactNum, headlineOf, postablePlatforms, subScores } from "@/lib/halo";
import { Dial, Ico, PlatIco, useMedia } from "./ui";

type UI = {
  staged: Set<string>;
  stage: (id: string, on: boolean) => void;
  /** Platforms this clip will post to. Long-form goes to TikTok by hand (D074/D079): the worker never posts it. */
  picksFor: (c: Clip) => Platform[];
  togglePick: (id: string, p: Platform) => void;
  postable: Platform[];
  /** False until the post-platforms migration is applied: then every connected account gets the post. */
  platformPick: boolean;
  heroPin: string | null;
  pinHero: (id: string | null) => void;
  pop: string | null;
  openPop: (id: string) => void;
  closePop: () => void;
  edit: string | null;
  openEditor: (id: string) => void;
  closeEditor: (saved: Clip | null) => void;
  edited: Set<string>;
  nudge: string | null;
  askPost: (ids: string[]) => void;
  askRevise: (id: string) => void;
  draft: (c: Clip) => string;
  setDraft: (id: string, v: string) => void;
  importOpen: boolean;
  setImportOpen: (on: boolean) => void;
  toast: (msg: string) => void;
  reject: (c: Clip) => void;
};

const Ctx = createContext<UI | null>(null);
export function useReview(): UI {
  const v = useContext(Ctx);
  if (!v) throw new Error("useReview outside ReviewProvider");
  return v;
}

export function ReviewProvider({ children }: { children: ReactNode }) {
  const { snap, act, demo } = useStore();
  const [staged, setStaged] = useState<Set<string>>(new Set());
  const [picks, setPicks] = useState<Record<string, Platform[]>>({});
  const [heroPin, pinHero] = useState<string | null>(null);
  const [pop, setPop] = useState<string | null>(null);
  const [edit, setEdit] = useState<string | null>(null);
  const [edited, setEdited] = useState<Set<string>>(new Set());
  const [nudge, setNudge] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<string[] | null>(null);
  const [revise, setRevise] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [importOpen, setImportOpen] = useState(false);
  const [msg, setMsg] = useState<{ t: string; k: number } | null>(null);

  const postable = useMemo(() => postablePlatforms(snap.destinations), [snap.destinations]);
  const platformPick = demo || snap.clips.some((c) => "post_platforms" in c);

  const toast = useCallback((t: string) => setMsg({ t, k: Date.now() }), []);
  useEffect(() => { if (!msg) return; const t = setTimeout(() => setMsg(null), 2600); return () => clearTimeout(t); }, [msg]);

  const stage = useCallback((id: string, on: boolean) => setStaged((s) => { const n = new Set(s); if (on) n.add(id); else n.delete(id); return n; }), []);
  const picksFor = useCallback((c: Clip): Platform[] => (c.category === "longform" ? ["tiktok"]
    : (platformPick ? (picks[c.id] ?? postable) : postable).filter((p) => postable.includes(p))), [picks, postable, platformPick]);
  const togglePick = useCallback((id: string, p: Platform) => {
    if (!platformPick || !postable.includes(p)) return;
    setPicks((m) => { const cur = m[id] ?? postable; return { ...m, [id]: cur.includes(p) ? cur.filter((x) => x !== p) : [...cur, p] }; });
  }, [platformPick, postable]);

  const openPop = useCallback((id: string) => setPop(id), []);
  const closePop = useCallback(() => setPop(null), []);
  const openEditor = useCallback((id: string) => { setPop(null); setEdit(id); }, []);
  const closeEditor = useCallback((saved: Clip | null) => {
    setEdit(null);
    if (!saved) return;
    setEdited((s) => new Set(s).add(saved.id));
    pinHero(saved.id);
    setNudge(saved.id);
    setTimeout(() => setNudge((n) => (n === saved.id ? null : n)), 2600);
  }, []);
  const askPost = useCallback((ids: string[]) => setConfirm(ids), []);
  const askRevise = useCallback((id: string) => setRevise(id), []);
  const draft = useCallback((c: Clip) => drafts[c.id] ?? headlineOf(c), [drafts]);
  const setDraft = useCallback((id: string, v: string) => setDrafts((d) => ({ ...d, [id]: v })), []);
  const reject = useCallback((c: Clip) => { act(c, "reject"); stage(c.id, false); setPop((p) => (p === c.id ? null : p)); }, [act, stage]);

  // A clip that left review (posted, rejected, gone) drops its local approve step and pin.
  useEffect(() => {
    const live = new Set(snap.clips.filter((c) => c.state === "pending_review" || c.state === "revise").map((c) => c.id));
    setStaged((s) => { const n = new Set([...s].filter((id) => live.has(id))); return n.size === s.size ? s : n; });
    if (heroPin && !live.has(heroPin)) pinHero(null);
  }, [snap.clips, heroPin]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (confirm) setConfirm(null); else if (revise) setRevise(null); else if (importOpen) setImportOpen(false);
      else if (pop) setPop(null); else if (edit) setEdit(null);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [confirm, revise, pop, edit, importOpen]);

  const value = useMemo<UI>(() => ({
    staged, stage, picksFor, togglePick, postable, platformPick, heroPin, pinHero, pop, openPop, closePop, edit, openEditor, closeEditor,
    edited, nudge, askPost, askRevise, draft, setDraft, importOpen, setImportOpen, toast, reject,
  }), [staged, stage, picksFor, togglePick, postable, platformPick, heroPin, pop, openPop, closePop, edit, openEditor, closeEditor,
    edited, nudge, askPost, askRevise, draft, setDraft, importOpen, toast, reject]);

  const byId = (id: string | null) => (id ? snap.clips.find((c) => c.id === id) ?? null : null);
  const popClip = byId(pop);
  const reviseClip = byId(revise);

  return (
    <Ctx.Provider value={value}>
      {children}
      {popClip && <ReviewPopup clip={popClip} />}
      {reviseClip && <ReviseDialog clip={reviseClip} onClose={() => setRevise(null)} />}
      {confirm && <ConfirmPost ids={confirm} onClose={() => setConfirm(null)} />}
      <UndoBar msg={msg?.t ?? null} />
    </Ctx.Provider>
  );
}

/** Why Post is not available yet, or null when it is. */
export function postBlock(c: Clip, ui: UI, canReview: boolean, waiting: boolean): string | null {
  if (!canReview) return "Only this clip's pod owner can post it.";
  if (waiting) return "Already on its way. Undo is in the bar below.";
  if (c.state === "revise") return "Your edit is re-rendering on the PC. Post once it is back.";
  if (c.state !== "pending_review") return `This clip is ${c.state.replace("_", " ")}.`;
  if (!ui.postable.length && c.category !== "longform") return "No posting account is connected yet (destinations).";
  if (!ui.staged.has(c.id)) return "Approve the clip before posting.";
  if (!ui.picksFor(c).length) return "Pick at least one platform first.";
  return null;
}

/** Approve / Revise / Reject / Edit clip. Approve only marks the clip ready; Post does the rest. */
export function ReviewActions({ clip, compact = false }: { clip: Clip; compact?: boolean }) {
  const ui = useReview();
  const { canReview, pending } = useStore();
  const mine = canReview(clip);
  const busy = clip.state !== "pending_review" || pending?.clip.id === clip.id;
  const on = ui.staged.has(clip.id);
  return (
    <div className="z-acts">
      <button type="button" className="z-btn z-w" disabled={!mine || busy} aria-pressed={on}
        onClick={() => { ui.stage(clip.id, !on); ui.toast(on ? "Approval taken back." : "Approved. Pick platforms, then post."); }}>
        {on ? <><Ico n="check" size={14} sw={2.6} />Approved</> : <>{compact ? "" : "✓ "}Approve</>}
      </button>
      <button type="button" className="z-btn" disabled={!mine || busy} onClick={() => ui.askRevise(clip.id)}>Revise</button>
      <button type="button" className="z-btn z-r" disabled={!mine || busy} onClick={() => ui.reject(clip)}>Reject</button>
      {!compact && <span className="z-sp" />}
      <button type="button" className="z-btn z-ed" disabled={!mine || busy} onClick={() => ui.openEditor(clip.id)}><Ico n="edit" size={15} sw={2.2} />Edit clip</button>
    </div>
  );
}

export function PostChips({ clip }: { clip: Clip }) {
  const ui = useReview();
  const picked = ui.picksFor(clip);
  if (clip.category === "longform") {
    return <div className="z-chips"><span className="z-pch z-on" data-pick="TikTok"><PlatIco p="tiktok" />TikTok · by hand</span></div>;
  }
  return (
    <div className={`z-chips${ui.nudge === clip.id ? " z-nudge" : ""}`}>
      {(["youtube", "tiktok", "x"] as Platform[]).map((p) => {
        const can = ui.postable.includes(p);
        const on = picked.includes(p);
        const label = PLATFORM_LABEL[p];
        return (
          <button key={p} type="button" className={`z-pch${on ? " z-on" : ""}${!ui.platformPick && can ? " z-lock" : ""}`} data-pick={label}
            aria-pressed={on} disabled={!can}
            title={!can ? (p === "tiktok" ? "TikTok is uploaded by hand (D074)" : `No active ${label} account`) : !ui.platformPick ? "Posts go to every connected account until the post-platforms migration is applied" : undefined}
            onClick={() => ui.togglePick(clip.id, p)}>
            <PlatIco p={p} size={p === "x" ? 13 : 14} />{p === "x" ? <span className="sr-only">X</span> : label}
          </button>
        );
      })}
    </div>
  );
}

export function PostButton({ clip, label = "Post →" }: { clip: Clip; label?: string }) {
  const ui = useReview();
  const { canReview, pending } = useStore();
  const why = postBlock(clip, ui, canReview(clip), pending?.clip.id === clip.id);
  return (
    <button type="button" className="z-btn z-post" aria-disabled={!!why} title={why ?? undefined}
      onClick={() => (why ? ui.toast(why) : ui.askPost([clip.id]))}>{label}</button>
  );
}

/** Headline box: edits re-render the clip (the headline is burned in), so a change is sent as an edit. */
export function HeadlineField({ clip, id }: { clip: Clip; id: string }) {
  const ui = useReview();
  const { sendEdit, canReview } = useStore();
  const [busy, setBusy] = useState(false);
  const v = ui.draft(clip);
  const changed = v.trim() !== headlineOf(clip).trim() && v.trim().length > 0;
  const can = canReview(clip) && clip.state === "pending_review";
  const apply = async () => {
    setBusy(true);
    const base = basePlan(clip);
    const ok = await sendEdit(clip, { ...base, headline: v.trim() }, base);
    setBusy(false);
    if (ok) { ui.closeEditor(clip); ui.toast("Headline sent. The PC re-renders the clip, then it comes back here."); }
  };
  return (
    <>
      <label className="z-lbl" htmlFor={id}>Headline{changed && <span style={{ color: "var(--warn)" }}>· changed</span>}</label>
      <div style={{ display: "flex", gap: 8 }}>
        <input className="z-fld" id={id} value={v} maxLength={90} disabled={!can} onChange={(e) => ui.setDraft(clip.id, e.target.value.toUpperCase())}
          onKeyDown={(e) => { if (e.key === "Enter" && changed && !busy) void apply(); }} />
        {changed && <button type="button" className="z-btn" disabled={busy} onClick={() => void apply()}>{busy ? "Sending…" : "Re-render"}</button>}
      </div>
    </>
  );
}

export function sourceLine(c: Clip, name: string, now: number): string {
  const plat = c.channel_key.split(":")[0];
  return [name, plat === "kick" ? "Kick" : plat === "twitch" ? "Twitch" : plat, clipLen(c.duration_s), `found ${agoShort(c.created_at, now)}`].join(" · ");
}

function ReviewPopup({ clip }: { clip: Clip }) {
  const ui = useReview();
  const { snap } = useStore();
  const now = useNow(30_000);
  const src = useMedia(clip.storage_path);
  const poster = useMedia(clip.thumb_path);
  const v = useRef<HTMLVideoElement>(null);
  const [t, setT] = useState(0);
  const [paused, setPaused] = useState(false);
  const [muted, setMuted] = useState(true);
  const s = subScores(clip);
  const who = snap.streamers.find((x) => x.id === clip.streamer_id)?.display_name ?? clip.channel_key.split(":")[1];
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => { close.current?.focus(); }, []);
  const on = ui.staged.has(clip.id);
  return (
    <div className="z-pop z-on" onClick={(e) => { if (e.target === e.currentTarget) ui.closePop(); }}>
      <div className={`z-popbx${on ? " z-approved" : ""}`} role="dialog" aria-modal="true" aria-label="Review clip">
        <button ref={close} type="button" className="z-x" aria-label="Close" onClick={ui.closePop}><Ico n="x" size={14} /></button>
        <div className="z-pvid">
          {src ? <video ref={v} src={src} poster={poster ?? undefined} playsInline loop autoPlay muted={muted}
            onTimeUpdate={(e) => setT(e.currentTarget.currentTime / (e.currentTarget.duration || 1))} />
            : <div className="z-empty" style={{ height: "100%" }}>Loading clip…</div>}
          <div className="z-pctl">
            <button type="button" aria-label={paused ? "Play" : "Pause"} onClick={() => { const el = v.current; if (!el) return; if (el.paused) { void el.play(); setPaused(false); } else { el.pause(); setPaused(true); } }}>{paused ? "▶" : "❚❚"}</button>
            <div className="z-pscrub" role="slider" aria-label="Seek" aria-valuenow={Math.round(t * 100)} aria-valuemin={0} aria-valuemax={100} tabIndex={0}
              onClick={(e) => { const el = v.current; if (!el) return; const r = e.currentTarget.getBoundingClientRect(); el.currentTime = ((e.clientX - r.left) / r.width) * (el.duration || 0); }}>
              <i style={{ width: `${t * 100}%` }} /></div>
            <button type="button" aria-label={muted ? "Sound on" : "Sound off"} onClick={() => setMuted((m) => !m)}>{muted ? "🔇" : "🔊"}</button>
          </div>
        </div>
        <div className="z-pmeta">
          <span className="z-lbl">{sourceLine(clip, who, now)}</span>
          <h3>{clip.title ?? clip.job_id}</h3>
          <div className="z-prow"><Dial score={clipScore(clip)} size={70} />
            <div className="z-pbrk">
              <span><b>{s.hook ?? "—"}</b>Hook</span><span><b>{s.payoff ?? "—"}</b>Payoff</span>
              <span><b>{s.trend ?? "—"}</b>Trend</span><span><b>{compactNum(s.views)}</b>Est. views</span>
            </div></div>
          <HeadlineField clip={clip} id="p-in" />
          <ReviewActions clip={clip} compact />
          <span className="z-lbl">Post to</span>
          <PostChips clip={clip} />
          <div className="z-acts"><PostButton clip={clip} label="Post now" />
            <span className="z-mut z-sm">{ui.platformPick ? "Posts right after you confirm (spacing per D088)." : "Posts to every connected account after you confirm."}</span></div>
        </div>
      </div>
    </div>
  );
}

const EXAMPLES = ["cut the first 2 seconds", "end right after the punchline", "bigger captions", "no sound effects", "under 20 seconds"];

function ReviseDialog({ clip, onClose }: { clip: Clip; onClose: () => void }) {
  const { act } = useStore();
  const ui = useReview();
  const [text, setText] = useState("");
  const [all, setAll] = useState(true);
  const note = cleanNote(text);
  const send = () => {
    if (!note) return;
    act(clip, "revise", note, all);
    ui.stage(clip.id, false);
    ui.closePop();
    onClose();
    ui.toast("Sent back to the editing agent.");
  };
  return (
    <div className="z-pop z-on z-cf" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="z-popbx z-sm" role="dialog" aria-modal="true" aria-label="Ask for a revision" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <h3 style={{ margin: 0 }}>What should change?</h3>
        <p className="z-mut z-sm" style={{ margin: 0 }}>{clip.title ?? clip.job_id}. Say it in plain English; the clipper re-renders it and sends it back here.</p>
        <textarea className="z-fld" autoFocus value={text} maxLength={500} rows={3} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send(); }} />
        <div className="z-chipx">{EXAMPLES.map((x) => (
          <button type="button" key={x} onClick={() => setText((t) => (t ? `${t.replace(/[.\s]+$/, "")}, ${x}` : x))}>{x}</button>))}</div>
        <label className="z-chk"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} />
          <span><b style={{ color: "var(--tx)" }}>Fix this on every clip.</b> Style fixes carry over to later clips (D078).</span></label>
        <div className="z-acts"><button type="button" className="z-btn z-w" disabled={!note} onClick={send}>Send revision</button>
          <button type="button" className="z-btn" onClick={onClose}>Cancel</button><span className="z-sp" /><span className="z-mut z-sm">{text.length}/500</span></div>
      </div>
    </div>
  );
}

function ConfirmPost({ ids, onClose }: { ids: string[]; onClose: () => void }) {
  const { snap, post, canReview, pending } = useStore();
  const ui = useReview();
  const clips = ids.map((id) => snap.clips.find((c) => c.id === id)).filter((c): c is Clip => !!c)
    .filter((c) => !postBlock(c, ui, canReview(c), pending?.clip.id === c.id));
  const go = useRef<HTMLButtonElement>(null);
  useEffect(() => { go.current?.focus(); }, []);
  const plats = [...new Set(clips.flatMap((c) => ui.picksFor(c)))];
  const names = (c: Clip) => c.category === "longform" ? "TikTok (you upload it by hand from Schedule)" : ui.picksFor(c).map((p) => PLATFORM_LABEL[p]).join(", ");
  const confirm = () => {
    for (const c of clips) { post(c, ui.picksFor(c)); ui.stage(c.id, false); }
    ui.closePop();
    onClose();
  };
  return (
    <div className="z-pop z-on z-cf" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="z-popbx z-sm" role="alertdialog" aria-modal="true" aria-label="Confirm post">
        <h3>{clips.length > 1 ? `Post these ${clips.length} clips?` : "Post this clip?"}</h3>
        {clips.length === 0 ? <p className="z-mut">Nothing is ready: approve a clip and pick at least one platform first.</p>
          : clips.length === 1
            ? <p className="z-mut">&ldquo;{clips[0].title ?? clips[0].job_id}&rdquo; goes public on <b style={{ color: "var(--tx)" }}>{names(clips[0])}</b>. You get {UNDO_MS / 1000} s to undo, then it can&rsquo;t be undone from here.</p>
            : <><p className="z-mut">Each clip goes public on the platforms picked for it. You get {UNDO_MS / 1000} s to undo the last one.</p>
              <ul className="z-cflist">{clips.map((c) => <li key={c.id}><span>{c.title ?? c.job_id}</span><span>{names(c)}</span></li>)}</ul></>}
        {!ui.platformPick && clips.length > 0 && <p className="z-note z-warn">Until the post-platforms migration is applied, every connected account gets the post.</p>}
        <div className="z-acts">
          <button ref={go} type="button" className="z-btn z-w" disabled={!clips.length} onClick={confirm}>
            Post to {plats.length} platform{plats.length === 1 ? "" : "s"}</button>
          <button type="button" className="z-btn" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

/** One bar for both: a short message, or the undo countdown for a post / reject / pod action waiting in the store. */
function UndoBar({ msg }: { msg: string | null }) {
  const { pending, later, undo } = useStore();
  const now = useNow(200);
  const open = !!(pending || later);
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("input,textarea,select")) return;
      if ((e.key === "z" && (e.ctrlKey || e.metaKey)) || e.key === "u") { e.preventDefault(); undo(); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, undo]);
  const shown = pending
    ? { verb: pending.action === "approve" ? `Posting to ${(pending.platforms ?? []).map((p) => PLATFORM_LABEL[p as Platform] ?? p).join(", ")}` : pending.action === "reject" ? "Rejected" : "Sent",
        label: pending.clip.title ?? pending.clip.job_id, until: pending.until }
    : later;
  if (shown) {
    const left = Math.max(0, shown.until - now);
    return (
      <div className="z-toast z-on" role="status">
        <span>{shown.verb} · <b>{shown.label}</b></span>
        <button type="button" onClick={undo}>Undo</button>
        <i className="z-tbar" style={{ transform: `scaleX(${left / UNDO_MS})` }} />
      </div>
    );
  }
  return <div className={`z-toast${msg ? " z-on" : ""}`} role="status">{msg}</div>;
}
