"use client";
import { useEffect } from "react";
import { UNDO_MS, useNow, useStore } from "@/lib/store";
import { Icon } from "./Icon";

export function UndoToast() {
  const { pending, later, undo } = useStore();
  const now = useNow(200);
  const open = !!(pending || later);
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => {
      if ((e.key === "z" && (e.ctrlKey || e.metaKey)) || e.key === "u") { e.preventDefault(); undo(); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, undo]);
  // Clip review first; then a waiting pod action (campaign decline, ledger step).
  const shown = pending
    ? { verb: pending.action === "approve" ? "Approved" : "Denied", label: pending.clip.title ?? pending.clip.job_id, until: pending.until }
    : later;
  if (!shown) return null;
  const left = Math.max(0, shown.until - now);
  return (
    <div className="toast" role="status">
      <span>{shown.verb} <b>{shown.label}</b></span>
      <button type="button" onClick={undo}><Icon name="undo" /> Undo</button>
      <i style={{ transform: `scaleX(${left / UNDO_MS})` }} />
    </div>
  );
}
