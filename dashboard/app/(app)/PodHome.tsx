"use client";
import { Money } from "@/components/pods/LedgerParts";
import Link from "next/link";
import { useState, type ReactNode } from "react";
import { Bars, LineChart } from "@/components/Charts";
import { compact, rankQueue, weekStats } from "@/lib/logic";
import { cents, isPodOwner, monthOf, statementsFor, stuckPosts, total, usd } from "@/lib/pods";
import { useNow, useStore } from "@/lib/store";

/** Oldest waiting clip turns warn colour past this age. */
const OLDEST_WARN_MS = 6 * 3_600_000;

function age(iso: string, now: number): string {
  return mins((now - Date.parse(iso)) / 60000);
}
function mins(n: number): string {
  const m = Math.max(0, Math.round(n));
  return m < 60 ? `${m}m` : `${Math.floor(m / 60)}h ${m % 60}m`;
}

/** One action row (Atlas pods §2): state dot, title + detail, control on the right. */
function ActionRow({ tone, title, detail, children }: { tone: "run" | "warn" | "ok" | ""; title: ReactNode; detail: ReactNode; children?: ReactNode }) {
  return (
    <li>
      <span className={`dotst${tone ? ` ${tone}` : ""}`} />
      <span className="tx"><b>{title}</b><span>{detail}</span></span>
      {children}
    </li>
  );
}

/** Pod home: what needs the pod now, in order (stuck posts, to approve, campaigns, earnings), charts below. */
export function PodHome({ podId }: { podId: string }) {
  const { snap, access, later, setPodCampaign } = useStore();
  const now = useNow(30_000);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const pod = snap.pods.find((p) => p.id === podId);
  const owner = isPodOwner(podId, access, snap.pods);

  const queue = rankQueue(snap.clips);
  const oldest = queue.reduce<string | null>((a, c) => (!a || c.created_at < a ? c.created_at : a), null);
  const clipById = new Map(snap.clips.map((c) => [c.id, c]));
  const stuck = stuckPosts(snap.postStats);
  const campById = new Map(snap.campaigns.map((c) => [c.id, c]));
  const suggested = snap.podCampaigns.filter((pc) => pc.status === "suggested" && later?.key !== `camp:${podId}:${pc.campaign_id}`);
  // Amounts are pod_statements columns; only added up across months here.
  const owed = total(snap.statements, (r) => r.owed_net_cents);
  const paidMonth = total(statementsFor(snap.statements, monthOf(now)), (r) => r.paid_net_cents);
  const rows = stuck.length + (queue.length ? 1 : 0) + suggested.length + (owed ? 1 : 0);

  const decide = async (campaign: string, status: "joined" | "declined", label: string) => {
    setBusy(campaign); setErr(null);
    const e = await setPodCampaign(podId, campaign, status, label);
    setBusy(null);
    if (e) setErr(e);
  };

  const week = weekStats(snap.clips, now);
  return (
    <>
      <section className="hero">
        <div>
          <h1>{pod?.name ?? "Pod"}<br /><b>{rows ? `${rows} thing${rows === 1 ? "" : "s"} need${rows === 1 ? "s" : ""} you.` : "All clear."}</b></h1>
          <p>{queue.length ? `${queue.length} clip${queue.length === 1 ? "" : "s"} waiting for review.` : "No clips waiting."}
            {owner ? "" : " You can see this pod; its owner approves clips and joins campaigns."}</p>
        </div>
      </section>

      {err && <div className="banner-line err" role="alert">{err}</div>}
      <section className="glass" aria-label="Needs you" style={{ marginTop: 34 }}>
        <div className="hd"><h3>Needs you</h3><span className="r">{rows}</span></div>
        {rows === 0 ? <p className="quiet">Nothing needs you right now.</p> : (
          <ul className="nextlist rows">
            {stuck.map((s) => {
              const c = clipById.get(s.clip_id);
              return (
                <ActionRow key={`${s.clip_id}|${s.platform}`} tone="warn" title={c?.title ?? c?.job_id ?? "Posted clip"}
                  detail={`Stuck on ${s.platform}: ${s.plays} plays at ${mins(s.hours_since_post * 60)} · read ${age(s.read_at, now)} ago`}>
                  <Link className="b" href={`/library?clip=${s.clip_id}`}>Open</Link>
                </ActionRow>
              );
            })}
            {queue.length > 0 && (
              <ActionRow tone="run" title={<><span className="sc">{queue.length}</span> to approve</>}
                detail={oldest ? <span className={now - Date.parse(oldest) > OLDEST_WARN_MS ? "st-revise" : undefined}>oldest {age(oldest, now)}</span> : ""}>
                <Link className="b ok" href="/review">Review</Link>
              </ActionRow>
            )}
            {suggested.map((pc) => {
              const c = campById.get(pc.campaign_id);
              const title = c?.title ?? "Suggested campaign";
              const reason = typeof pc.scout?.reason === "string" ? pc.scout.reason : c?.recommendation ?? "";
              const line = [c?.cpm_usd != null ? `$${c.cpm_usd.toFixed(2)} CPM` : null, c?.cap_usd != null ? `cap $${compact(c.cap_usd)}` : null, reason]
                .filter(Boolean).join(" · ");
              return (
                <ActionRow key={pc.campaign_id} tone="" title={title} detail={line || "Suggested by the scout"}>
                  {owner ? (
                    <>
                      <button type="button" className="b ok" disabled={busy === pc.campaign_id} onClick={() => void decide(pc.campaign_id, "joined", title)}>Join</button>
                      <button type="button" className="b" disabled={busy === pc.campaign_id} onClick={() => void decide(pc.campaign_id, "declined", title)}>Decline</button>
                    </>
                  ) : <span className="pill">suggested</span>}
                </ActionRow>
              );
            })}
            {owed !== 0 && (
              <ActionRow tone="ok" title="Earnings" detail={`owed ${usd(owed)} · paid ${usd(paidMonth)} this month`}>
                <Link className="b" href="/statements">Statements</Link>
              </ActionRow>
            )}
          </ul>
        )}
      </section>

      <div className="row2e" style={{ marginTop: 18 }}>
        <Link href="/statements" className="glass stat hot">
          <span className="lab">Owed</span>
          <Money n={owed} sm />
        </Link>
        <Link href="/statements" className="glass stat">
          <span className="lab">Paid this month</span>
          <Money n={paidMonth} sm />
        </Link>
      </div>

      <div className="sec"><h2>Trends</h2><span>last 7 days · this pod</span></div>
      <div className="row2">
        <div className="glass">
          <div className="hd"><h3>Clips made vs approved</h3></div>
          <LineChart height={220} labels={week.days.map((d) => d.label)} empty="No clips this week"
            series={week.days.some((d) => d.made) ? [
              { name: "Made", color: "var(--acc)", values: week.days.map((d) => d.made) },
              { name: "Approved", color: "var(--c2)", values: week.days.map((d) => d.approved) },
            ] : []} />
          <div className="legend"><span><i style={{ background: "var(--acc)" }} />Made</span><span><i style={{ background: "var(--c2)" }} />Approved</span></div>
        </div>
        <div className="glass">
          <div className="hd"><h3>Clips made per day</h3></div>
          {week.days.some((d) => d.made)
            ? <Bars height={220} data={week.days.map((d) => ({ label: d.label, value: d.made, color: d.today ? "var(--acc)" : undefined }))} />
            : <p className="quiet">No clips this week.</p>}
        </div>
      </div>
    </>
  );
}
