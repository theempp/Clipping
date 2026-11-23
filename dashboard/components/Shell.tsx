"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { PC_NAME } from "@/lib/env";
import { openSubmissions, pcState, rankQueue } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { BUDGET_USD, monthSpend, streamerViews } from "@/lib/view";
import { Avatar } from "./Avatar";
import { Ring } from "./Charts";
import { Icon } from "./Icon";
import { UndoToast } from "./UndoToast";
import { SleepBanner } from "./WakeToggle";

export const PAGES = [
  { href: "/", label: "Overview", icon: "grid", main: true },
  { href: "/review", label: "Review", icon: "review", main: true },
  { href: "/analytics", label: "Analytics", icon: "chart", main: true },
  { href: "/streamers", label: "Streamers", icon: "user", main: true },
  { href: "/editor", label: "Editor", icon: "film", main: true },
  { href: "/schedule", label: "Schedule", icon: "cal", main: false },
  { href: "/campaigns", label: "Campaigns", icon: "flag", main: false },
  { href: "/library", label: "Library", icon: "folder", main: false },
  { href: "/settings", label: "Settings", icon: "gear", main: false },
  // Pods (Phase 4). Icons reuse existing glyphs: Atlas GAP 4 (no money/ledger icon in the set yet).
  { href: "/ledger", label: "Ledger", icon: "queue", main: false, pods: "admin" },
  { href: "/statements", label: "Statements", icon: "text", main: false, pods: "all" },
] as const;
type Page = (typeof PAGES)[number];
/** Pages this user sees: pod pages only with pods on; Ledger only for the admin. */
function usePages(): readonly Page[] {
  const { podsOn, access } = useStore();
  return PAGES.filter((p) => !("pods" in p) || (podsOn && (p.pods === "all" || !!access?.admin)));
}
// On a phone the dock keeps four pages; the rest sit behind "More".
const PHONE = new Set(["/", "/review", "/streamers", "/editor"]);

const isOn = (path: string, href: string) => (href === "/" ? path === "/" : path === href || path.startsWith(`${href}/`));

export function Shell({ children }: { children: ReactNode }) {
  const { snap, demo, error, ready, signOut, setAwake, pollLive, podsOn, access } = useStore();
  const now = useNow(5000);
  const path = usePathname();
  const router = useRouter();
  const queue = rankQueue(snap.clips);
  const awake = snap.control.awake;
  const st = pcState(snap.heartbeat, awake, now);
  const gpu = snap.heartbeat?.status.gpu;
  const disk = snap.heartbeat?.status.disk;
  const spend = monthSpend(snap);
  const [menu, setMenu] = useState<null | "fab" | "more">(null);
  const [panel, setPanel] = useState<null | "search" | "alerts">(null);

  // Power-on / power-off sweep: only when the switch changes after load, never on first paint.
  const [fx, setFx] = useState<"" | "fx-on" | "fx-off">("");
  const lastAwake = useRef<boolean | null>(null);
  useEffect(() => {
    if (!ready) return;
    const was = lastAwake.current;
    lastAwake.current = awake;
    if (was === null || was === awake) return;
    setFx(awake ? "fx-on" : "fx-off");
    const t = setTimeout(() => setFx(""), awake ? 2200 : 900);
    return () => clearTimeout(t);
  }, [awake, ready]);

  useEffect(() => { setMenu(null); setPanel(null); }, [path]);
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setMenu(null); setPanel(null); }
      const t = e.target as HTMLElement;
      if (e.key === "/" && !t.closest("input,textarea,select,[contenteditable]")) { e.preventDefault(); setPanel("search"); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  const alerts = useAlerts();
  const pages = usePages();

  if (error === "not-owner") {
    return (
      <main className="gate">
        <div className="gate-card glass">
          <h1>Not allowed</h1>
          <p>{podsOn ? "This account is signed in but is not in any pod. Clipp is invite-only." : "This account is signed in but is not the owner. Clipp is private."}</p>
          <button className="b ok lg" onClick={() => void signOut()}>Sign out</button>
        </div>
      </main>
    );
  }

  const dockLink = (p: Page) => {
    const on = isOn(path, p.href);
    return (
      <Link key={p.href} href={p.href} className={`${on ? "on" : ""}${PHONE.has(p.href) ? "" : " extra"}`}
        aria-label={p.label} aria-current={on ? "page" : undefined}>
        <Icon name={p.icon} size={18} />
        {p.href === "/review" && queue.length > 0 && <em>{queue.length}</em>}
        <span className="tip">{p.label}</span>
      </Link>
    );
  };

  return (
    <div className={`app ${!ready ? "booting" : awake ? "awake" : "asleep"}${fx ? ` ${fx}` : ""}`}>
      <div className="aurora" aria-hidden="true" />
      {fx === "fx-on" && <div className="ignite" aria-hidden="true"><i /></div>}

      <nav className="dock" aria-label="Pages">
        <button type="button" className="fab" aria-label="Quick actions" aria-expanded={menu === "fab"}
          onClick={() => setMenu((m) => (m === "fab" ? null : "fab"))}><Icon name="plus" size={20} /></button>
        {pages.map(dockLink)}
        <button type="button" className="more-b" aria-label="More pages" aria-expanded={menu === "more"}
          onClick={() => setMenu((m) => (m === "more" ? null : "more"))}><Icon name="more" size={20} /></button>
        {menu && <button type="button" className="scrim" aria-label="Close menu" onClick={() => setMenu(null)} />}
        {menu === "fab" && (
          <div className="menu" role="menu">
            <button role="menuitem" onClick={() => { setMenu(null); router.push(queue[0] ? `/editor?clip=${queue[0].id}` : "/editor"); }}>
              <Icon name="film" /> Edit the top clip</button>
            <button role="menuitem" onClick={() => { setMenu(null); router.push("/review"); }}><Icon name="review" /> Open review queue</button>
            <button role="menuitem" onClick={() => { setMenu(null); void pollLive(true); }}><Icon name="refresh" /> Refresh live numbers</button>
            <button role="menuitem" onClick={() => { setMenu(null); void setAwake(!awake); }}><Icon name="power" /> {awake ? `Put ${PC_NAME} to sleep` : `Wake ${PC_NAME} up`}</button>
          </div>
        )}
        {menu === "more" && (
          <div className="menu" role="menu">
            {pages.filter((p) => !PHONE.has(p.href)).map((p) => (
              <Link key={p.href} href={p.href} role="menuitem" className={isOn(path, p.href) ? "on" : ""}><Icon name={p.icon} /> {p.label}</Link>
            ))}
          </div>
        )}
      </nav>

      <aside className="rdock" aria-label="Machine">
        <div><Ring pct={st === "offline" ? 0 : gpu?.util ?? 0} label={`GPU ${gpu?.util ?? 0}%`} />GPU</div>
        <div><Ring pct={disk?.used_pct ?? 0} color="var(--c2)" text={disk?.used_pct == null ? "—" : undefined} label={`Disk ${disk?.used_pct ?? "unknown"}%`} />Disk</div>
        <div><Ring pct={(spend.total / BUDGET_USD) * 100} color="var(--c3)" label={`AI spend ${Math.round((spend.total / BUDGET_USD) * 100)}% of budget`} />AI $</div>
      </aside>

      <div className="wrap">
        <header className="top">
          <Link href="/" className="brand" aria-label="Clipp home">zwocl<b>i</b>ppe{demo && <small>demo</small>}
            {podsOn && access && !access.admin && access.pods[0] && <small>{access.pods[0].name}</small>}</Link>
          {podsOn && <PodSwitcher />}
          <span className="sp" />
          <nav className="pillnav" aria-label="Main">
            {pages.filter((p) => p.main).map((p) => (
              <Link key={p.href} href={p.href} className={isOn(path, p.href) ? "on" : ""} aria-current={isOn(path, p.href) ? "page" : undefined}>{p.label}</Link>
            ))}
          </nav>
          <span className="sp" />
          <button type="button" className="icb" aria-label="Search (press /)" onClick={() => setPanel("search")}><Icon name="search" size={18} /></button>
          <button type="button" className="icb" aria-label={`Alerts (${alerts.length})`} onClick={() => setPanel("alerts")}>
            <Icon name="bell" size={18} />{alerts.length > 0 && <em />}
          </button>
        </header>

        {error && error !== "not-owner" && <div className="banner-line err" role="alert">{error}</div>}
        {ready && !awake && <SleepBanner />}
        {!ready ? <div className="loading">Loading…</div> : children}
        {demo && <p className="foot">Demo data. Nothing here is saved or posted.</p>}
      </div>

      {panel === "search" && <SearchPanel onClose={() => setPanel(null)} />}
      {panel === "alerts" && <AlertsPanel alerts={alerts} onClose={() => setPanel(null)} />}
      <UndoToast />
    </div>
  );
}

/** Admin pod switcher (Atlas pods §1): All, then one button per pod. Hidden for members and when there is one pod. */
function PodSwitcher() {
  const { access, pod, setPod, snap, ready } = useStore();
  if (!access?.admin || snap.pods.length < 2) return null;
  return (
    <div className="seg" role="tablist" aria-label="Pod">
      <button type="button" role="tab" aria-selected={pod === null} className={pod === null ? "on" : ""} disabled={!ready}
        onClick={() => setPod(null)}>All</button>
      {snap.pods.map((p) => (
        <button key={p.id} type="button" role="tab" aria-selected={pod === p.id} className={pod === p.id ? "on" : ""} disabled={!ready}
          onClick={() => setPod(p.id)}>{p.name}</button>
      ))}
    </div>
  );
}

type Alert = { id: string; text: string; href: string; tone: "warn" | "run" | "ok" };

function useAlerts(): Alert[] {
  const { snap } = useStore();
  const now = useNow(5000);
  const out: Alert[] = [];
  for (const s of openSubmissions(snap.submissions, now)) {
    out.push({ id: s.id, text: `Submit window open: ${Math.ceil((Date.parse(s.deadline_at) - now) / 60000)} min left`, href: "/", tone: "warn" });
  }
  const q = rankQueue(snap.clips).length;
  if (q) out.push({ id: "q", text: `${q} clip${q === 1 ? "" : "s"} waiting on you`, href: "/review", tone: "run" });
  const st = pcState(snap.heartbeat, snap.control.awake, now);
  if (st === "offline" && snap.control.awake) out.push({ id: "pc", text: `${PC_NAME} is not reporting`, href: "/settings", tone: "warn" });
  return out;
}

function Overlay({ label, onClose, children }: { label: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="search" role="dialog" aria-modal="true" aria-label={label} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="search-box">{children}</div>
    </div>
  );
}

function AlertsPanel({ alerts, onClose }: { alerts: Alert[]; onClose: () => void }) {
  return (
    <Overlay label="Alerts" onClose={onClose}>
      <div className="hd" style={{ padding: "6px 8px 0" }}><h3>Alerts</h3><button className="b" onClick={onClose}>Close</button></div>
      <ul>
        {alerts.length === 0 && <li><div className="mut">All clear.</div></li>}
        {alerts.map((a) => (
          <li key={a.id}><Link href={a.href} onClick={onClose}><span className={`dotst ${a.tone}`} /><span>{a.text}</span></Link></li>
        ))}
      </ul>
    </Overlay>
  );
}

function SearchPanel({ onClose }: { onClose: () => void }) {
  const { snap } = useStore();
  const all = usePages();
  const now = useNow(30_000);
  const [q, setQ] = useState("");
  const views = useMemo(() => streamerViews(snap, now), [snap, now]);
  const t = q.trim().toLowerCase();
  const hits = useMemo(() => {
    const found = all.filter((p) => p.label.toLowerCase().includes(t)).map((p) => ({ k: p.href, href: p.href, label: p.label, meta: "page", s: null }));
    const ss = views.filter((v) => v.s.display_name.toLowerCase().includes(t))
      .map((v) => ({ k: v.s.id, href: `/streamers/${v.s.slug}`, label: v.s.display_name, meta: v.live ? "live" : "streamer", s: v.s }));
    const cs = snap.clips.filter((c) => (c.title ?? c.job_id).toLowerCase().includes(t)).slice(0, 8)
      .map((c) => ({ k: c.id, href: c.state === "pending_review" ? `/review?clip=${c.id}` : `/library?clip=${c.id}`, label: c.title ?? c.job_id, meta: c.state.replace("_", " "), s: null }));
    return t ? [...found, ...ss, ...cs] : [...ss.slice(0, 5), ...found];
  }, [t, views, snap.clips, all]);
  return (
    <Overlay label="Search" onClose={onClose}>
      <input autoFocus placeholder="Search streamers, clips, pages" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
      <ul>
        {hits.map((h) => (
          <li key={h.k}><Link href={h.href} onClick={onClose}>
            {h.s ? <Avatar s={h.s} size={26} /> : <Icon name="arrow" />}<span>{h.label}</span><small>{h.meta}</small>
          </Link></li>
        ))}
        {hits.length === 0 && <li><div className="mut">Nothing matches “{q}”.</div></li>}
      </ul>
    </Overlay>
  );
}
