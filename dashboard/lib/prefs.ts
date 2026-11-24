"use client";
// Player preferences, kept in this browser only (localStorage). Nothing here reaches the PC or Supabase.
import { useEffect, useState } from "react";

export type Prefs = {
  /** Start review players with sound on. Browsers may still block sound until you click once. */
  sound: boolean;
  /** Default playback speed for review players and the editor. */
  rate: number;
  /** Loop clips in the review hero and popup. */
  loop: boolean;
};
export const DEFAULT_PREFS: Prefs = { sound: false, rate: 1, loop: true };
const KEY = "clipp.prefs.v1";
const EVT = "clipp-prefs";

export function readPrefs(): Prefs {
  if (typeof window === "undefined") return DEFAULT_PREFS;
  try {
    const raw = JSON.parse(window.localStorage.getItem(KEY) ?? "{}") as Partial<Prefs>;
    return {
      sound: typeof raw.sound === "boolean" ? raw.sound : DEFAULT_PREFS.sound,
      rate: typeof raw.rate === "number" && raw.rate >= 0.25 && raw.rate <= 2 ? raw.rate : DEFAULT_PREFS.rate,
      loop: typeof raw.loop === "boolean" ? raw.loop : DEFAULT_PREFS.loop,
    };
  } catch { return DEFAULT_PREFS; }
}

export function writePrefs(p: Partial<Prefs>): Prefs {
  const next = { ...readPrefs(), ...p };
  window.localStorage.setItem(KEY, JSON.stringify(next));
  window.dispatchEvent(new Event(EVT));
  return next;
}

/** Current prefs, updated when Settings (or another tab) changes them. */
export function usePrefs(): [Prefs, (p: Partial<Prefs>) => void] {
  const [p, setP] = useState<Prefs>(DEFAULT_PREFS);
  useEffect(() => {
    const sync = () => setP(readPrefs());
    sync();
    window.addEventListener(EVT, sync);
    window.addEventListener("storage", sync);
    return () => { window.removeEventListener(EVT, sync); window.removeEventListener("storage", sync); };
  }, []);
  return [p, (x) => setP(writePrefs(x))];
}
