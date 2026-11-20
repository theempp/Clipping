"use client";
import { useEffect } from "react";
import { UNDO_MS, useNow, useStore } from "@/lib/store";
import { Icon } from "./Icon";

export function UndoToast() {
  const { pending, undo } = useStore();
  const now = useNow(200);
  useEffect(() => {
    if (!pending) return;
    const h = (e: KeyboardEvent) => {
      if ((e.key === "z" && (e.ctrlKey || e.metaKey)) || e.key === "u") { e.preventDefault(); undo(); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [pending, undo]);
  if (!pending) return null;
  const left = Math.max(0, pending.until - now);
  const verb = pending.action === "approve" ? "Approved" : "Denied";
  return (
    <div className="toast" role="status">
      <span>{verb} <b>{pending.clip.title ?? pending.clip.job_id}</b></span>
      <button type="button" onClick={undo}><Icon name="undo" /> Undo</button>
      <i style={{ transform: `scaleX(${left / UNDO_MS})` }} />
    </div>
  );
}
