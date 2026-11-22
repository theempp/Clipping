"use client";
import { useEffect, useRef, useState } from "react";
import { cleanNote } from "@/lib/logic";
import { useStore } from "@/lib/store";
import type { Clip } from "@/lib/types";
import { Icon } from "./Icon";

const EXAMPLES = ["smoother zooms, only on big moments", "no zooms", "under 30 seconds", "no sound effects", "blue captions"];

/** Deny / Revise / Approve, keys D / R / A. Revise opens the plain-English box in the flow, under the buttons. */
export function ReviewDock({ clip }: { clip: Clip | null }) {
  const { act } = useStore();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [all, setAll] = useState(true);  // D078: the fix also applies to every upcoming clip
  const area = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { setOpen(false); setText(""); }, [clip?.id]);
  useEffect(() => { if (open) area.current?.focus(); }, [open]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (!clip || e.metaKey || e.ctrlKey || e.altKey || t.closest("input,textarea,select,[contenteditable]")) return;
      const k = e.key.toLowerCase();
      if (k === "a") { e.preventDefault(); act(clip, "approve"); }
      else if (k === "d") { e.preventDefault(); act(clip, "reject"); }
      else if (k === "r") { e.preventDefault(); setOpen(true); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [clip, act]);

  const note = cleanNote(text);
  const send = () => {
    if (!clip || !note) return;
    act(clip, "revise", note, all);
    setOpen(false); setText("");
  };

  return (
    <div className="dock-wrap">
      <div className="dock" aria-label="Review actions">
        <button type="button" disabled={!clip} className="deny" onClick={() => clip && act(clip, "reject")}>
          <Icon name="x" /> Deny <kbd>D</kbd>
        </button>
        <button type="button" disabled={!clip} className={`rev${open ? " sel" : ""}`} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          <Icon name="pen" /> Revise <kbd>R</kbd>
        </button>
        <button type="button" disabled={!clip} className="approve" onClick={() => clip && act(clip, "approve")}>
          <Icon name="check" /> Approve <kbd>A</kbd>
        </button>
      </div>
      {open && clip && (
        <div className="revise" role="group" aria-label="Ask for a revision">
          <div className="revise-h">
            <b>What should change?</b>
            <button type="button" className="x" aria-label="Close" onClick={() => setOpen(false)}><Icon name="x" /></button>
          </div>
          <textarea ref={area} value={text} maxLength={500} rows={3}
            placeholder="Say it in plain English. The clipper re-renders and sends it back here."
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setOpen(false);
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send();
            }} />
          <div className="chips">
            {EXAMPLES.map((x) => (
              <button type="button" key={x} onClick={() => setText((t) => (t ? `${t.replace(/[.\s]+$/, "")}, ${x}` : x))}>{x}</button>
            ))}
          </div>
          <label className={`allfix${all ? " on" : ""}`}>
            <input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} />
            <span className="sw" aria-hidden="true"><i /></span>
            <span><b>Fix this on every clip</b> · style fixes (zooms, camera, sound, captions, length) carry over,
              and clips already waiting get re-edited before you see them</span>
          </label>
          <div className="revise-f">
            <span>{text.length}/500 · Ctrl+Enter sends</span>
            <button type="button" className="btn light sm" disabled={!note} onClick={send}>Send revision</button>
          </div>
        </div>
      )}
    </div>
  );
}
