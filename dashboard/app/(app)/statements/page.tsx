"use client";
import { Money } from "@/components/pods/LedgerParts";
import { useState } from "react";
import { EntryTable, StatusWord } from "@/components/pods/LedgerParts";
import { ago } from "@/lib/logic";
import { cents, entryMonth, eventText, podName, recentMonths, statementsFor, total } from "@/lib/pods";
import { useNow, useStore } from "@/lib/store";

const monthLabel = (m: string) => new Date(`${m}T00:00:00Z`).toLocaleDateString(undefined, { month: "short", year: "numeric", timeZone: "UTC" });

/** Read-only statement for one pod (D092): monthly totals from pod_statements, itemized entries, audit log. */
export default function StatementsPage() {
  const { podsOn, pod, snap, ready, error } = useStore();
  if (!podsOn) return <section className="hero"><div><h1>Statements</h1><p>Statements come with pods.</p></div></section>;
  if (!pod) {
    return (
      <section className="hero"><div><h1>Statements</h1>
        <p>{snap.pods.length ? "Pick a pod in the top bar to see its statement." : "No pod to show."}</p></div></section>
    );
  }
  return (
    <>
      {error && error !== "not-owner" && <div className="banner-line err" role="alert">{error}</div>}
      {!ready ? <section className="glass"><p className="quiet">Loading…</p></section> : <Statement key={pod} podId={pod} />}
    </>
  );
}

function Statement({ podId }: { podId: string }) {
  const { snap } = useStore();
  const now = useNow(60_000);
  const months = recentMonths(snap.statements, now);
  const [month, setMonth] = useState(months[0]);
  const rows = statementsFor(snap.statements, month);
  // One pod_statements row per pod and month; total() only covers the shape of the array.
  const pending = total(rows, (r) => r.pending_net_cents);
  const owed = total(rows, (r) => r.owed_net_cents);
  const paid = total(rows, (r) => r.paid_net_cents);
  const items = snap.ledger.filter((e) => entryMonth(e) === month);
  const ids = new Set(items.map((e) => e.id));
  const events = snap.ledgerEvents.filter((ev) => ids.has(ev.entry_id));
  const empty = rows.length === 0;

  return (
    <>
      <section className="hero" style={{ marginBottom: 28 }}>
        <div><h1>Statements<br /><b>{podName(snap.pods, podId)} · {monthLabel(month)}</b></h1>
          <p>Read-only. Amounts are after the 15% agency cut. Zo records each payout and marks it paid with the transfer reference.</p></div>
        <div className="seg" role="tablist" aria-label="Month">
          {months.map((m) => <button key={m} type="button" className={m === month ? "on" : ""} onClick={() => setMonth(m)}>{monthLabel(m)}</button>)}
        </div>
      </section>

      <div className="row3">
        <div className="glass stat"><span className="lab">Pending</span><Money n={pending} />
          <div className="sub">{empty ? "No activity" : <><StatusWord status="pending" /> not yet landed</>}</div></div>
        <div className="glass stat"><span className="lab">Owed</span><Money n={owed} />
          <div className="sub">{empty ? "No activity" : <><StatusWord status="cleared" /> + <StatusWord status="approved" /></>}</div></div>
        <div className="glass stat"><span className="lab">Paid</span><Money n={paid} />
          <div className="sub">{empty ? "No activity" : <><StatusWord status="paid" /> transferred</>}</div></div>
      </div>

      <div className="sec"><h2>Items</h2><span>{items.length}</span></div>
      <section className="glass" aria-label="Items">
        {items.length === 0 ? <p className="quiet">No entries this month.</p> : <EntryTable rows={items} showDate />}
      </section>

      <div className="sec"><h2>Audit log</h2><span>every change, append-only</span></div>
      <section className="glass" aria-label="Audit log">
        {events.length === 0 ? <p className="quiet">No changes yet.</p> : (
          <ul className="nextlist rows">
            {events.map((ev) => (
              <li key={ev.id}>
                <span className="tx"><b>{eventText(ev)}</b><span>{ev.actor} · {ago(ev.at, now)}</span></span>
                <StatusWord status={ev.to_status} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
