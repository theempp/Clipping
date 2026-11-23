"use client";
import { Fragment, useEffect, useState, type ReactNode } from "react";
import { cents, podName, reversedIds, usd } from "@/lib/pods";
import { useStore } from "@/lib/store";
import type { LedgerEntry } from "@/lib/types";

/** Phone layout switch for ledger tables (Atlas pods §3: table above 720px, .tt-list at or below). */
export function useNarrow(px = 720): boolean {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const m = window.matchMedia(`(max-width: ${px}px)`);
    const h = () => setNarrow(m.matches);
    h();
    m.addEventListener("change", h);
    return () => m.removeEventListener("change", h);
  }, [px]);
  return narrow;
}

// Atlas pods §3 status mapping. Paid = .pill.st-scheduled is Atlas GAP 1 (decision pending).
const PILL: Record<LedgerEntry["status"], string> = { pending: "pill warn", cleared: "pill run", approved: "pill ok", paid: "pill st-scheduled" };

export function StatusPill({ e }: { e: Pick<LedgerEntry, "status" | "source"> }) {
  if (e.source === "reversal") return <><span className="pill bad">reversal</span> <StatusWord status={e.status} /></>;
  return <span className={PILL[e.status]}>{e.status}</span>;
}
export function StatusWord({ status }: { status: LedgerEntry["status"] }) {
  return <span className={PILL[status]}>{status}</span>;
}

/** Money tile number; negative totals show the minus and the --bad colour. */
export function Money({ n, sm }: { n: number; sm?: boolean }) {
  return <div className={`num${sm ? " sm" : ""} tnum`} style={n < 0 ? { color: "var(--bad)" } : undefined}>{n < 0 ? "-" : ""}<small className="pre">$</small>{cents(Math.abs(n))}</div>;
}

const refText = (e: LedgerEntry) => (e.reverses_id ? `reverses #${e.reverses_id.slice(0, 8)}` : e.source_ref);
const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });

/** Itemized entries. Amounts are the database's columns, formatted only. `actions`/`below` add admin controls. */
export function EntryTable({ rows, showPod, showDate, actions, below }: {
  rows: LedgerEntry[]; showPod?: boolean; showDate?: boolean;
  actions?: (e: LedgerEntry) => ReactNode; below?: (e: LedgerEntry) => ReactNode;
}) {
  const { snap } = useStore();
  const narrow = useNarrow();
  const camp = new Map(snap.campaigns.map((c) => [c.id, c.title]));
  const title = (e: LedgerEntry) => (e.campaign_id ? camp.get(e.campaign_id) ?? "Campaign" : "—");
  // Looked up over the whole ledger, so a filtered table still marks reversed originals.
  const rev = reversedIds(snap.ledger);
  const byOrig = new Map(snap.ledger.filter((r) => r.reverses_id).map((r) => [r.reverses_id as string, r.id]));
  const refCell = (e: LedgerEntry) => {
    const r = rev.has(e.id) ? byOrig.get(e.id) : undefined;
    return <>{refText(e)}{r && <span className="quiet"> · reversed by #{r.slice(0, 8)}</span>}</>;
  };
  const bad = (e: LedgerEntry) => (e.source === "reversal" ? "bad" : undefined);

  if (narrow) {
    return (
      <ul className="tt-list">
        {rows.map((e) => (
          <li key={e.id} className="tt-row">
            <div className="tt-top">
              <span className="tx"><b>{title(e)}</b><span>{[showPod ? podName(snap.pods, e.pod_id) : null, showDate ? day(e.created_at) : null, ""].filter((x) => x !== null).join(" · ")}{refCell(e)}</span></span>
              <StatusPill e={e} />
            </div>
            <dl className="metrics">
              <div><dt>Gross</dt><dd className={bad(e)}>{usd(e.gross_cents)}</dd></div>
              <div><dt>Cut</dt><dd className={bad(e)}>{usd(e.agency_cut_cents)}</dd></div>
              <div><dt>Net</dt><dd className={bad(e)}>{usd(e.pod_net_cents)}</dd></div>
            </dl>
            {actions && <div className="tt-post">{actions(e)}</div>}
            {below?.(e)}
          </li>
        ))}
      </ul>
    );
  }
  const cols = 6 + (showPod ? 1 : 0) + (showDate ? 1 : 0) + (actions ? 1 : 0);
  return (
    <div className="scroll-x">
      <table className="tbl">
        <thead>
          <tr>
            {showDate && <th>Date</th>}{showPod && <th>Pod</th>}<th>Campaign</th><th>Source ref</th>
            <th>Gross</th><th>Cut 15%</th><th>Pod net</th><th>Status</th>{actions && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((e) => {
            const extra = below?.(e);
            return (
              <Fragment key={e.id}>
                <tr>
                  {showDate && <td>{day(e.created_at)}</td>}
                  {showPod && <td>{podName(snap.pods, e.pod_id)}</td>}
                  <td>{title(e)}</td>
                  <td>{refCell(e)}</td>
                  <td className={`tnum${e.source === "reversal" ? " bad" : ""}`}>{usd(e.gross_cents)}</td>
                  <td className={`tnum${e.source === "reversal" ? " bad" : ""}`}>{usd(e.agency_cut_cents)}</td>
                  <td className={`tnum${e.source === "reversal" ? " bad" : ""}`}>{usd(e.pod_net_cents)}</td>
                  <td><StatusPill e={e} /></td>
                  {actions && <td><div className="chips">{actions(e)}</div></td>}
                </tr>
                {extra && <tr><td colSpan={cols}>{extra}</td></tr>}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
