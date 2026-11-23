"use client";
import { useEffect, useState } from "react";
import { useStore } from "@/lib/store";
import type { Streamer } from "@/lib/types";

export const BRAIN_KEYS = [
  ["chat_spike", "Chat spike"], ["voice_peak", "Voice peak"], ["chat_words", "Chat words"],
  ["viewer_clips", "Viewer-made clips"], ["approved_match", "Approved-clip match"],
] as const;
export const BRAIN_DEFAULT: Record<string, number> = { chat_spike: 70, voice_peak: 55, chat_words: 75, viewer_clips: 35, approved_match: 60 };

export function useBrain(streamerId: string | undefined) {
  const { snap } = useStore();
  const b = snap.brains.find((x) => x.streamer_id === streamerId);
  return { weights: { ...BRAIN_DEFAULT, ...b?.weights }, words: b?.words ?? [], learned: !!b, updated: b?.updated_at ?? null };
}

/** What the detector weighs for this streamer (Streamer Brain). `edit` turns the bars into sliders that save. */
export function BrainWeights({ s, edit = false }: { s: Streamer; edit?: boolean }) {
  const { setBrain } = useStore();
  const { weights, words, learned } = useBrain(s.id);
  const [draft, setDraft] = useState(weights);
  const [wordText, setWordText] = useState(words.join(", "));
  useEffect(() => { setDraft(weights); setWordText(words.join(", ")); }, [s.id, JSON.stringify(weights), words.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps
  const dirty = JSON.stringify(draft) !== JSON.stringify(weights) || wordText !== words.join(", ");
  return (
    <div>
      {BRAIN_KEYS.map(([k, label]) => (
        <div key={k} className={`br${edit ? " edit" : ""}`}>
          <span>{label}{k === "chat_words" && words.length > 0 && !edit ? ` (“${words.slice(0, 2).join("”, “")}”)` : ""}</span>
          {edit
            ? <input type="range" min={0} max={100} value={draft[k]} aria-label={`${label} weight`}
                onChange={(e) => setDraft((d) => ({ ...d, [k]: Number(e.target.value) }))} />
            : <div className="tr"><i style={{ width: `${weights[k]}%` }} /></div>}
          <b>{edit ? draft[k] : weights[k]}</b>
        </div>
      ))}
      {!learned && <p className="quiet">Default weights. Nothing has been saved for this streamer yet.</p>}
      {edit && (
        <>
          <label className="field" style={{ marginTop: 10 }}>Chat words that mean a moment (comma separated)
            <input type="text" value={wordText} onChange={(e) => setWordText(e.target.value)} placeholder="CLIP, NO WAY" />
          </label>
          <button type="button" className="b ok" disabled={!dirty}
            onClick={() => void setBrain(s.id, draft, wordText.split(",").map((w) => w.trim()).filter(Boolean).slice(0, 20))}>
            Save {s.display_name}’s brain
          </button>
          <p className="quiet" style={{ fontSize: 11, marginBottom: 0 }}>The PC reads these within a minute. Chat spike, voice peak, chat words and your words change what it clips; viewer-made clips and approved-clip match are saved only, with no detector signal yet.</p>
        </>
      )}
    </div>
  );
}
