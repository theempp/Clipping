"use client";
import { Money } from "@/components/pods/LedgerParts";
import { useMemo, useState } from "react";
import { EntryTable } from "@/components/pods/LedgerParts";
import { NEXT_STEP, cents, parseCents, reversedIds, total } from "@/lib/pods";
import { useStore } from "@/lib/store";
import type { LedgerEntry, LedgerStatus } from "@/lib/types";

const STATUSES: [LedgerStatus | "all", string][] = [["all", "All"], ["pending", "Pending"], ["cleared", "Cleared"], ["approved", "Approved"], ["paid", "Paid"]];
type Open = { id: string; kind: "paid" | "reverse"; text: string };

/** Admin ledger (D092): records payouts and their steps. The database computes the 15% cut and net and guards every step. */
export default function LedgerPage() {
  const { podsOn, access } = useStore();
  if (!podsOn || !access?.admin) {
    return (
      <section className="hero"><div><h1>Ledger</h1><p>The ledger is for the agency admin. Your pod&apos;s money is on Statements.</p></div></section>
    );
  }
  return <Ledger />;
}

function Ledger() {
  const { snap, pod, later, ledgerStep, ledgerReverse } = useStore();
  const [st, setSt] = useState<LedgerStatus | "all">("all");
  const [podF, setPodF] = useState("all");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Open | null>(null);
  const [fail, setFail] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  const reversed = reversedIds(snap.ledger);
  const rows = useMemo(() => {
    const camp = new Map(snap.campaigns.map((c) => [c.id, c.title]));
    const t = q.trim().toLowerCase();
    return snap.ledger.filter((e) => (st === "all" || e.status === st) && (pod || podF === "all" || e.pod_id === podF)
      && (!t || `${e.source_ref} ${e.campaign_id ? camp.get(e.campaign_id) ?? "" : ""} ${e.note ?? ""}`.toLowerCase().includes(t)));
  }, [snap.ledger, snap.campaigns, st, pod, podF, q]);

  // Totals add the database's per-row amounts; no rate math in the browser.
  const gross = total(rows, (e) => e.gross_cents);
  const cut = total(rows, (e) => e.agency_cut_cents);
  const net = total(rows, (e) => e.pod_net_cents);
  const unpaid = total(rows.filter((e) => e.status !== "paid"), (e) => e.pod_net_cents);

  const run = async (e: LedgerEntry, f: () => Promise<string | null>) => {
    setBusy(e.id);
    const err = await f();
    setBusy(null);
    setFail((m) => { const n = { ...m }; if (err) n[e.id] = err; else delete n[e.id]; return n; });
    if (!err) setOpen(null);
  };

  const actions = (e: LedgerEntry) => {
    const step = NEXT_STEP[e.status];
    const waiting = later?.key === `ledger:${e.id}` || busy === e.id;
    return (
      <>
        {step === "cleared" && <button type="button" className="b" disabled={waiting} onClick={() => void run(e, () => ledgerStep(e, "cleared"))}>Mark cleared</button>}
        {step === "approved" && <button type="button" className="b ok" disabled={waiting} onClick={() => void run(e, () => ledgerStep(e, "approved"))}>Approve</button>}
        {step === "paid" && <button type="button" className={`b acc${open?.id === e.id && open.kind === "paid" ? " sel" : ""}`} disabled={waiting}
          aria-expanded={open?.id === e.id && open.kind === "paid"} onClick={() => setOpen({ id: e.id, kind: "paid", text: "" })}>Mark paid</button>}
        {e.source !== "reversal" && !reversed.has(e.id) && (
          <button type="button" className="b" disabled={waiting} aria-expanded={open?.id === e.id && open.kind === "reverse"}
            onClick={() => setOpen({ id: e.id, kind: "reverse", text: "" })}>Reverse</button>
        )}
      </>
    );
  };

  const below = (e: LedgerEntry) => {
    const o = open?.id === e.id ? open : null;
    const err = fail[e.id];
    if (!o && !err) return null;
    return (
      <>
        {o && (
          <div className="revise" role="group" aria-label={o.kind === "paid" ? "Mark paid" : "Reverse entry"}>
            {o.kind === "paid"
              ? <input className="in" autoFocus value={o.text} maxLength={120} placeholder="Transfer reference (required)" aria-label="Transfer reference"
                  onChange={(x) => setOpen({ ...o, text: x.target.value })} />
              : <textarea autoFocus value={o.text} rows={2} maxLength={500} placeholder="Why is this reversed? (required)" aria-label="Reason"
                  onChange={(x) => setOpen({ ...o, text: x.target.value })} />}
            <div className="ft">
              <span>{o.kind === "paid"
                ? "Records the transfer you already made. Paid is final; this does not send money."
                : `Adds a reversing entry of -$${cents(e.gross_cents)} gross. The original stays in the ledger.`}</span>
              <span className="chips">
                <button type="button" className="b" onClick={() => setOpen(null)}>Cancel</button>
                <button type="button" className="b acc" disabled={!o.text.trim() || busy === e.id}
                  onClick={() => void run(e, () => (o.kind === "paid" ? ledgerStep(e, "paid", o.text) : ledgerReverse(e, o.text)))}>
                  {o.kind === "paid" ? "Confirm paid" : "Confirm reversal"}</button>
              </span>
            </div>
          </div>
        )}
        {err && <p className="fixing bad" role="alert">{err}</p>}
      </>
    );
  };

  return (
    <>
      <section className="hero" style={{ marginBottom: 28 }}>
        <div><h1>Ledger<br /><b>{rows.length} entr{rows.length === 1 ? "y" : "ies"}.</b></h1>
          <p>Record payouts as they land, then clear, approve and mark paid with the transfer reference. Corrections are reversing entries.</p></div>
      </section>

      <div className="row4">
        <div className="glass stat"><span className="lab">Gross</span><Money n={gross} sm /></div>
        <div className="glass stat"><span className="lab">15% cut</span><Money n={cut} sm /></div>
        <div className="glass stat"><span className="lab">Pod net</span><Money n={net} sm /></div>
        <div className="glass stat"><span className="lab">Unpaid</span><Money n={unpaid} sm /></div>
      </div>

      <AddEntry defaultPod={pod} />

      <div className="filters" style={{ marginTop: 18 }}>
        <div className="seg" role="tablist" aria-label="Status">
          {STATUSES.map(([k, l]) => <button key={k} type="button" className={st === k ? "on" : ""} onClick={() => setSt(k)}>{l}</button>)}
        </div>
        {!pod && (
          <select className="in" value={podF} onChange={(e) => setPodF(e.target.value)} aria-label="Pod" style={{ flex: "0 1 200px" }}>
            <option value="all">Every pod</option>
            {snap.pods.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        )}
        <input className="in" type="search" placeholder="Search ref, campaign, note" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search entries" />
      </div>

      <section className="glass" aria-label="Entries">
        {rows.length === 0 ? <p className="quiet">No entries for this filter.</p>
          : <EntryTable rows={rows} showPod={!pod} actions={actions} below={below} />}
      </section>
    </>
  );
}

/** ledger_add: one payout for one pod. Gross is typed in dollars and sent as whole cents. */
function AddEntry({ defaultPod }: { defaultPod: string | null }) {
  const { snap, ledgerAdd } = useStore();
  const [podId, setPodId] = useState(defaultPod ?? "");
  const [campaign, setCampaign] = useState("");
  const [ref, setRef] = useState("");
  const [gross, setGross] = useState("");
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [checked, setChecked] = useState(false);
  const target = defaultPod ?? podId;
  const amount = parseCents(gross);
  const ready = !!target && !!ref.trim() && amount != null && !busy;
  const campaigns = snap.campaigns;

  const add = async () => {
    setChecked(true);
    if (!ready || amount == null) return;
    setBusy(true);
    const err = await ledgerAdd(target, campaign || null, ref.trim(), amount, note.trim() || null);
    setBusy(false);
    if (err) { setMsg({ ok: false, text: err }); return; }
    setMsg({ ok: true, text: `Added ${ref.trim()} as pending.` });
    setRef(""); setGross(""); setNote(""); setChecked(false);
  };

  return (
    <section className="glass" aria-label="Add entry" style={{ marginTop: 18 }}>
      <div className="hd"><h3>Add entry</h3><span className="r">starts pending</span></div>
      <div className="tt-form">
        {!defaultPod && (
          <label>Pod
            <select className="in" value={podId} onChange={(e) => setPodId(e.target.value)}>
              <option value="">Pick a pod</option>
              {snap.pods.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select></label>
        )}
        <label>Campaign
          <select className="in" value={campaign} onChange={(e) => setCampaign(e.target.value)}>
            <option value="">None</option>
            {campaigns.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select></label>
        <label>Source ref<input className="in" value={ref} maxLength={120} placeholder="Payout id" onChange={(e) => setRef(e.target.value)} /></label>
        <label>Gross $<input className="in" inputMode="decimal" value={gross} placeholder="0.00" onBlur={() => setChecked(true)} onChange={(e) => setGross(e.target.value)} /></label>
        <label>Note<input className="in" value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} /></label>
        <button type="button" className="b acc" disabled={!ready} onClick={() => void add()}>{busy ? "Adding…" : "Add"}</button>
      </div>
      {checked && amount == null && <p className="fixing bad">Gross must be more than 0, like 125.50 (at most 2 decimals).</p>}
      {msg && <p className={msg.ok ? "quiet" : "fixing bad"} role="status">{msg.text}</p>}
    </section>
  );
}
