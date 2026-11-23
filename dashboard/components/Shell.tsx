"use client";
// Halo Pro shell (D116): the whole screen is the console. Page dots in the top bar, quick actions in the bottom dock,
// "Always on" in place of Wake Up. Live / Pods & ledger / Stats keep their own content inside the same frame.
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { PC_NAME } from "@/lib/env";
import { openSubmissions, pcState, rankQueue } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { PLATFORM_LABEL, agoShort, upcomingPosts, type Platform } from "@/lib/halo";
import { streamerViews } from "@/lib/view";
import { LinkBox } from "./LinkBox";
import { ReviewProvider, useReview } from "./halo/review";
import { Ico, SvgDefs } from "./halo/ui";

type Page = { href: string; label: string; icon?: string; match: string[] };

function usePages() {
  const { podsOn, access } = useStore();
  const money: Page = podsOn
    ? { href: access?.admin ? "/ledger" : "/statements", label: "Pods & ledger", icon: "money", match: ["/ledger", "/statements"] }
    : { href: "/campaigns", label: "Pods & ledger", icon: "money", match: ["/campaigns"] };
  const dots: Page[] = [
    { href: "/streamers", label: "Live", icon: "live", match: ["/streamers", "/live"] },
    { href: "/", label: "Review", icon: "review", match: ["/", "/review", "/editor"] },
    money,
    { href: "/analytics", label: "Stats", icon: "stats", match: ["/analytics"] },
  ];
  const more: Page[] = [
    { href: "/library", label: "Library", match: ["/library"] },
    { href: "/schedule", label: "Schedule", match: ["/schedule"] },
    ...(podsOn ? [{ href: "/campaigns", label: "Campaigns", match: ["/campaigns"] }] : []),
    ...(podsOn && access?.admin ? [{ href: "/statements", label: "Statements", match: ["/statements"] }] : []),
    { href: "/settings", label: "Settings", match: ["/settings"] },
  ];
  return { dots, more };
}
const isOn = (path: string, p: Page) => p.match.some((m) => (m === "/" ? path === "/" : path === m || path.startsWith(`${m}/`)));

export function Shell({ children }: { children: ReactNode }) {
  const { error, ready, signOut, podsOn } = useStore();
  if (error === "not-owner") {
    return (
      <>
        <div className="z-amb" aria-hidden="true" />
        <main className="z-gate"><div className="z-popbx z-sm"><h3>Not allowed</h3>
          <p className="z-mut">{podsOn ? "This account is signed in but is not in any pod. Zwoclippe is invite-only." : "This account is signed in but is not the owner. Zwoclippe is private."}</p>
          <div className="z-acts"><button type="button" className="z-btn z-w" onClick={() => void signOut()}>Sign out</button></div></div></main>
      </>
    );
  }
  return <ReviewProvider><Frame ready={ready}>{children}</Frame></ReviewProvider>;
}

function Frame({ ready, children }: { ready: boolean; children: ReactNode }) {
  const path = usePathname();
  const review = path === "/";
  const ui = useReview();
  // One light-up sweep on load (body.z-waking), nothing else: the dashboard is always on.
  useEffect(() => {
    document.body.classList.add("z-waking");
    const t = setTimeout(() => document.body.classList.remove("z-waking"), 1800);
    return () => { clearTimeout(t); document.body.classList.remove("z-waking"); };
  }, []);
  useEffect(() => { document.body.classList.toggle("z-editing", !!ui.edit && review); }, [ui.edit, review]);
  return (
    <>
      <SvgDefs />
      <div className="z-amb" aria-hidden="true" /><div className="z-grid" aria-hidden="true" /><div className="z-flash" aria-hidden="true" />
      <div className="z-app">
        <TopBar />
        <main className="z-main">
          {!ready ? <div className="z-loading">Loading…</div> : review ? children : <div className="legacy z-legacy">{children}</div>}
        </main>
        <BottomBar />
      </div>
      <ErrorLine />
      {ui.importOpen && <ImportPopup onClose={() => ui.setImportOpen(false)} />}
    </>
  );
}

function ErrorLine() {
  const { error } = useStore();
  const [hidden, setHidden] = useState<string | null>(null);
  if (!error || error === "not-owner" || hidden === error) return null;
  return <div className="z-err" role="alert"><span>{error}</span><button type="button" aria-label="Dismiss" onClick={() => setHidden(error)}>✕</button></div>;
}

function Clock() {
  const now = useNow(15_000);
  const [ok, setOk] = useState(false);
  useEffect(() => setOk(true), []);
  if (!ok) return <small>&nbsp;</small>;
  const d = new Date(now);
  return <small>{d.toLocaleDateString("en-US", { weekday: "long" })} · {d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}</small>;
}

function TopBar() {
  const { snap, demo } = useStore();
  const path = usePathname();
  const now = useNow(5000);
  const { dots } = usePages();
  const queue = rankQueue(snap.clips).length;
  const st = pcState(snap.heartbeat, now);
  const agents = st === "offline" ? 0 : (snap.heartbeat?.status.capturing ?? snap.heartbeat?.status.live ?? []).length;
  return (
    <header className="z-top">
      <Link href="/" className="z-brand" aria-label="Zwoclippe, Review"><span className="z-mk">Z</span><div>Zwoclippe{demo && <span className="z-mut" style={{ fontSize: 11, fontWeight: 700, marginLeft: 6 }}>demo</span>}<Clock /></div></Link>
      <nav className="z-dots" aria-label="Pages">
        {dots.map((p) => {
          const on = isOn(path, p);
          return (
            <Link key={p.label} href={p.href} className={on ? "z-on" : ""} aria-current={on ? "page" : undefined}>
              <Ico n={p.icon ?? "review"} />{p.label}{p.href === "/" && queue > 0 && <span className="z-ct">{queue}</span>}
            </Link>
          );
        })}
      </nav>
      <div className="z-tr">
        <span className={`z-onair${st === "offline" ? " z-down" : ""}`} title={st === "offline" ? `${PC_NAME} is not reporting` : `${PC_NAME} is always on (D116)`}>
          <span className="z-pl"><i /></span>{st === "offline" ? "PC offline" : "Always on"} <small>· {agents} agent{agents === 1 ? "" : "s"}</small>
        </span>
        <Search />
        <Alerts />
        <Account />
      </div>
    </header>
  );
}

function useOutside(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) close(); };
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    document.addEventListener("mousedown", h); document.addEventListener("keydown", k);
    return () => { document.removeEventListener("mousedown", h); document.removeEventListener("keydown", k); };
  }, [open, close]);
  return ref;
}

function Search() {
  const { snap } = useStore();
  const router = useRouter();
  const ui = useReview();
  const path = usePathname();
  const { dots, more } = usePages();
  const now = useNow(30_000);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const ref = useOutside(open, () => setOpen(false));
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.key === "/" && !t.closest("input,textarea,select,[contenteditable]")) { e.preventDefault(); input.current?.focus(); setOpen(true); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);
  const t = q.trim().toLowerCase();
  const views = useMemo(() => streamerViews(snap, now), [snap, now]);
  const hits = useMemo(() => {
    if (!t) return [];
    const pages = [...dots, ...more].filter((p) => p.label.toLowerCase().includes(t)).map((p) => ({ k: `p${p.href}${p.label}`, label: p.label, meta: "page", go: () => router.push(p.href) }));
    const ss = views.filter((v) => v.s.display_name.toLowerCase().includes(t)).map((v) => ({ k: v.s.id, label: v.s.display_name, meta: v.live ? "live" : "streamer", go: () => router.push(`/streamers/${v.s.slug}`) }));
    const cs = snap.clips.filter((c) => (c.title ?? c.job_id).toLowerCase().includes(t)).slice(0, 8).map((c) => ({
      k: c.id, label: c.title ?? c.job_id, meta: c.state.replace("_", " "),
      go: () => { if (c.state === "pending_review") { if (path === "/") ui.openPop(c.id); else router.push(`/?clip=${c.id}`); } else router.push(`/library?clip=${c.id}`); },
    }));
    return [...ss, ...cs, ...pages].slice(0, 10);
  }, [t, views, snap.clips, dots, more, router, path, ui]);
  return (
    <div className="z-srch-wrap z-rel" ref={ref}>
      <label className="z-srch"><Ico n="search" size={15} />
        <input ref={input} placeholder="Search clips" aria-label="Search clips, streamers and pages" value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
          onKeyDown={(e) => { if (e.key === "Enter" && hits[0]) { hits[0].go(); setOpen(false); setQ(""); } }} />
        <kbd>/</kbd></label>
      {open && t && (
        <div className="z-pop-menu z-menu-down" role="listbox" aria-label="Search results" style={{ left: 0, right: "auto", width: "min(360px, 80vw)" }}>
          {hits.map((h) => <button key={h.k} type="button" role="option" aria-selected={false} onClick={() => { h.go(); setOpen(false); setQ(""); }}>{h.label}<small>{h.meta}</small></button>)}
          {hits.length === 0 && <div className="z-empty">Nothing matches &ldquo;{q}&rdquo;.</div>}
        </div>
      )}
    </div>
  );
}

function Alerts() {
  const { snap } = useStore();
  const now = useNow(5000);
  const [open, setOpen] = useState(false);
  const ref = useOutside(open, () => setOpen(false));
  const items: { k: string; text: string; href: string }[] = [];
  for (const s of openSubmissions(snap.submissions, now)) items.push({ k: s.id, text: `Submit window open: ${Math.ceil((Date.parse(s.deadline_at) - now) / 60000)} min left`, href: "/schedule" });
  const q = rankQueue(snap.clips).length;
  if (q) items.push({ k: "q", text: `${q} clip${q === 1 ? "" : "s"} waiting on you`, href: "/" });
  const failed = snap.clips.filter((c) => c.state === "revise" && c.revise_failed).length;
  if (failed) items.push({ k: "rf", text: `${failed} revision${failed === 1 ? "" : "s"} failed QA on the PC`, href: "/library" });
  const fails = snap.clips.filter((c) => c.state === "failed").length;
  if (fails) items.push({ k: "pf", text: `${fails} post${fails === 1 ? "" : "s"} failed`, href: "/library" });
  if (pcState(snap.heartbeat, now) === "offline") items.push({ k: "pc", text: `${PC_NAME} is not reporting`, href: "/settings" });
  return (
    <div className="z-rel" ref={ref}>
      <button type="button" className={`z-bell${items.length ? "" : " z-quiet"}`} aria-label={`Notifications (${items.length})`} aria-expanded={open} onClick={() => setOpen((o) => !o)}><Ico n="bell" size={16} /></button>
      {open && (
        <div className="z-pop-menu z-menu-down" role="menu">
          <h6>Notifications</h6>
          {items.map((a) => <Link key={a.k} href={a.href} role="menuitem" onClick={() => setOpen(false)}>{a.text}</Link>)}
          {items.length === 0 && <div className="z-empty">All clear.</div>}
        </div>
      )}
    </div>
  );
}

function Account() {
  const { signOut, demo, access, pod, setPod, snap, podsOn } = useStore();
  const [open, setOpen] = useState(false);
  const ref = useOutside(open, () => setOpen(false));
  return (
    <div className="z-rel" ref={ref}>
      <button type="button" className="z-me" aria-label="Account" aria-expanded={open} onClick={() => setOpen((o) => !o)}>Z</button>
      {open && (
        <div className="z-pop-menu z-menu-down" role="menu">
          {podsOn && access?.admin && snap.pods.length > 1 && <>
            <h6>Pod in view</h6>
            <button type="button" role="menuitemradio" aria-checked={pod === null} className={pod === null ? "z-on" : ""} onClick={() => { setPod(null); setOpen(false); }}>All pods</button>
            {snap.pods.map((p) => (
              <button key={p.id} type="button" role="menuitemradio" aria-checked={pod === p.id} className={pod === p.id ? "z-on" : ""}
                onClick={() => { setPod(p.id); setOpen(false); }}>{p.name}<small>{p.status}</small></button>
            ))}
            <h6>Account</h6>
          </>}
          {podsOn && access && !access.admin && access.pods[0] && <h6>{access.pods[0].name}</h6>}
          <Link href="/settings" role="menuitem" onClick={() => setOpen(false)}>Settings</Link>
          {!demo && <button type="button" role="menuitem" onClick={() => void signOut()}>Sign out</button>}
          {demo && <div className="z-empty">Demo data. Nothing here is saved or posted.</div>}
        </div>
      )}
    </div>
  );
}

function BottomBar() {
  const { snap, pollLive, requestClip } = useStore();
  const ui = useReview();
  const router = useRouter();
  const path = usePathname();
  const now = useNow(1000);
  const { more } = usePages();
  const [menu, setMenu] = useState<null | "new" | "clip">(null);
  const ref = useOutside(!!menu, () => setMenu(null));
  const st = pcState(snap.heartbeat, now);
  const queue = rankQueue(snap.clips).length;
  const staged = [...ui.staged];
  const live = streamerViews(snap, now).filter((v) => v.live);
  const up = upcomingPosts(snap.clips, snap.publications);
  const nextPl = (up[0]?.post_platforms?.length ? up[0].post_platforms : ui.postable).map((p) => PLATFORM_LABEL[p as Platform] ?? p).join(", ");
  const clipNow = async (slug: string, name: string) => {
    setMenu(null);
    const err = await requestClip(slug, 60);
    ui.toast(err ? `Clip request failed: ${err}` : `Asked the PC for the last 60 s of ${name}. It lands in the queue after render and QA.`);
  };
  const seen = snap.heartbeat ? Math.max(0, Math.round((now - Date.parse(snap.heartbeat.seen_at)) / 1000)) : null;
  return (
    <footer className="z-bot">
      <div className="z-l"><span className={`z-dot${st === "offline" ? " z-warn" : ""}`} />
        {st === "offline" ? `${PC_NAME} not reporting${snap.heartbeat ? ` · last seen ${agoShort(snap.heartbeat.seen_at, now)}` : ""}` : `All systems on · synced ${seen ?? 0} s ago`}</div>
      <div className="z-dock z-rel" role="toolbar" aria-label="Quick actions" ref={ref}>
        <button type="button" className="z-o" aria-label="More pages and actions" aria-expanded={menu === "new"} onClick={() => setMenu((m) => (m === "new" ? null : "new"))}>+</button>
        <button type="button" className="z-hot" disabled={!live.length} title={live.length ? undefined : "No one is live right now"} aria-expanded={menu === "clip"}
          onClick={() => (live.length === 1 ? void clipNow(live[0].s.slug, live[0].s.display_name) : setMenu((m) => (m === "clip" ? null : "clip")))}>
          <span className="z-rec" />Clip last 60 s</button>
        <button type="button" onClick={() => ui.setImportOpen(true)}><Ico n="download" />Import VOD</button>
        <button type="button" onClick={() => {
          if (path !== "/") { router.push("/"); return; }
          const el = document.getElementById("queue");
          el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
          (el?.querySelector(".z-qi") as HTMLElement | null)?.focus();
        }}><Ico n="list" />Open queue <em>{queue}</em></button>
        <button type="button" disabled={!staged.length} title={staged.length ? undefined : "Approve clips first; Post batch posts every approved clip after one confirm"}
          onClick={() => ui.askPost(staged)}><Ico n="send" />Post batch <em>{staged.length}</em></button>
        {menu === "new" && (
          <div className="z-pop-menu z-menu-up" role="menu">
            <h6>Pages</h6>
            {more.map((p) => <Link key={p.href} href={p.href} role="menuitem" onClick={() => setMenu(null)}>{p.label}</Link>)}
            <h6>Actions</h6>
            <button type="button" role="menuitem" onClick={() => { setMenu(null); ui.setImportOpen(true); }}>Paste a VOD or clip link</button>
            <button type="button" role="menuitem" onClick={() => { setMenu(null); void pollLive(true); ui.toast("Asked the platforms for fresh numbers."); }}>Refresh live numbers</button>
          </div>
        )}
        {menu === "clip" && (
          <div className="z-pop-menu z-menu-up" role="menu" style={{ left: 50 }}>
            <h6>Clip the last 60 s of</h6>
            {live.map((v) => <button key={v.s.id} type="button" role="menuitem" onClick={() => void clipNow(v.s.slug, v.s.display_name)}>{v.s.display_name}<small>{v.game ?? "live"}</small></button>)}
          </div>
        )}
      </div>
      <div className="z-r">{up.length ? <>Next post <b>&nbsp;in line&nbsp;</b> · {nextPl || "no account"}</> : <>Next post <b>&nbsp;none queued</b></>}</div>
    </footer>
  );
}

function ImportPopup({ onClose }: { onClose: () => void }) {
  return (
    <div className="z-pop z-on" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="z-popbx z-wide" role="dialog" aria-modal="true" aria-label="Import a VOD or clip link" style={{ display: "block" }}>
        <button type="button" className="z-x" aria-label="Close" onClick={onClose}><Ico n="x" size={14} /></button>
        <h3 style={{ margin: "0 0 4px" }}>Import VOD</h3>
        <p className="z-mut z-sm" style={{ margin: "0 0 12px" }}>Paste a Twitch, Kick, YouTube or X link. The PC cuts clips from it and they land in the queue as pending. Nothing posts.</p>
        <div className="legacy"><LinkBox /></div>
      </div>
    </div>
  );
}
