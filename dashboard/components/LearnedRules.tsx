"use client";
import { isMemberOnly } from "@/lib/pods";
import { useStore } from "@/lib/store";

/** Standing fixes learned from Zo's revision notes (D078), and what the PC is re-editing for them. */
export function LearnedRules() {
  const { snap, setRuleActive, podsOn, access } = useStore();
  const canTune = !isMemberOnly(podsOn, access);
  const fixing = snap.clips.filter((c) => c.state === "pending_review" && c.fixing).length;
  const pendingNotes = snap.revisions.filter((r) => !r.resolved_at).length;
  if (!snap.rules.length && !fixing) return null;
  return (
    <div className="learned" aria-label="Learned from your notes">
      <h3 style={{ margin: 0, font: "600 14px var(--fd)" }}>Learned from your notes</h3>
      {fixing > 0 && <p className="fixing">Re-editing {fixing} waiting clip{fixing === 1 ? "" : "s"} with your fixes. They come back here when done.</p>}
      <ul>
        {snap.rules.slice(0, 5).map((r) => (
          <li key={r.id} className={r.active ? "" : "off"}>
            <span className="rt2"><b>{r.label}</b><span title={r.note}>“{r.note}”{r.fixed_count ? ` · fixed ${r.fixed_count}` : ""}</span></span>
            {canTune && (
              <button type="button" role="switch" aria-checked={r.active} className="swb"
                aria-label={`${r.active ? "Stop" : "Start"} applying: ${r.label}`} onClick={() => void setRuleActive(r.id, !r.active)}>
                <span className={`sw sm${r.active ? " on" : ""}`} />
              </button>
            )}
          </li>
        ))}
      </ul>
      {pendingNotes > 0 && !fixing && <p className="quiet">{pendingNotes} note{pendingNotes === 1 ? "" : "s"} waiting for the PC to read.</p>}
    </div>
  );
}
