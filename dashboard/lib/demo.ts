// Sample day for demo mode (D057). Times are relative to page load so the
// countdown and "live for" clocks move. Nothing here touches the network.
import { entryMonth } from "./pods.ts";
import type { Access, BrainWeights, Campaign, Candidate, Clip, LedgerEntry, LedgerEvent, LiveStat, LongformVideo, Pod, PodCampaign, PodStatement,
  PostStat, Publication, Snapshot, StatPoint, Streamer } from "./types.ts";

// ---- Demo stand-ins for the database (D057). Live mode never runs these: Postgres generates the cut and net
// columns and the pod_statements view; the UI only displays them. ----
const pgRound = (x: number) => Math.sign(x) * Math.round(Math.abs(x));
type NewEntry = Pick<LedgerEntry, "id" | "pod_id" | "source_ref" | "campaign_id" | "gross_cents" | "created_at"> & Partial<LedgerEntry>;
/** A ledger_entries row as the database would return it (generated columns filled in). */
export function demoEntry(p: NewEntry): LedgerEntry {
  const rate = p.agency_rate ?? 0.15;
  const cut = pgRound(p.gross_cents * rate);
  return { source: "campaign", status: "pending", note: null, reverses_id: null, cleared_at: null, approved_at: null,
    paid_at: null, paid_ref: null, ...p, agency_rate: rate, agency_cut_cents: cut, pod_net_cents: p.gross_cents - cut };
}
let evSeq = 0;
/** What the ledger_audit trigger would write for this row. */
export function demoEvent(e: LedgerEntry, from: LedgerEntry["status"] | null, at: string): LedgerEvent {
  evSeq += 1;
  return { id: evSeq, entry_id: e.id, pod_id: e.pod_id,
    op: from === null ? "insert" : "update", from_status: from, to_status: e.status, actor: "admin", actor_id: "demo-zo",
    row_after: { ...e }, at };
}
/** pod_statements view over demo entries. */
export function demoStatements(rows: LedgerEntry[]): PodStatement[] {
  const by = new Map<string, PodStatement>();
  for (const e of rows) {
    const month = entryMonth(e);
    const k = `${e.pod_id}|${month}`;
    const s = by.get(k) ?? { pod_id: e.pod_id, month, entries: 0, gross_cents: 0, agency_cut_cents: 0, pod_net_cents: 0,
      pending_net_cents: 0, owed_net_cents: 0, paid_net_cents: 0 };
    s.entries += 1; s.gross_cents += e.gross_cents; s.agency_cut_cents += e.agency_cut_cents; s.pod_net_cents += e.pod_net_cents;
    if (e.status === "pending") s.pending_net_cents += e.pod_net_cents;
    else if (e.status === "paid") s.paid_net_cents += e.pod_net_cents;
    else s.owed_net_cents += e.pod_net_cents;
    by.set(k, s);
  }
  return [...by.values()].sort((a, b) => b.month.localeCompare(a.month));
}

function demoLedger(iso: (msAgo: number) => string): { ledger: LedgerEntry[]; ledgerEvents: LedgerEvent[] } {
  const h = 3600_000;
  const steps = (e: LedgerEntry, at: string[]): LedgerEvent[] => {
    const order: LedgerEntry["status"][] = ["pending", "cleared", "approved", "paid"];
    const n = order.indexOf(e.status);
    return at.slice(0, n + 1).map((t, i) => demoEvent({ ...e, status: order[i] }, i === 0 ? null : order[i - 1], t));
  };
  const e1 = demoEntry({ id: "le-1", pod_id: "pod-1", source_ref: "CR-1042", campaign_id: "c1", gross_cents: 40000, status: "paid",
    created_at: iso(30 * h), cleared_at: iso(28 * h), approved_at: iso(26 * h), paid_at: iso(20 * h), paid_ref: "T-881" });
  const e2 = demoEntry({ id: "le-2", pod_id: "pod-1", source_ref: "CR-1077", campaign_id: "c1", gross_cents: 50000, status: "approved",
    created_at: iso(12 * h), cleared_at: iso(10 * h), approved_at: iso(9 * h) });
  const e3 = demoEntry({ id: "le-3", pod_id: "pod-1", source_ref: "WH-220", campaign_id: "c2", gross_cents: 30000, created_at: iso(3 * h) });
  const e4 = demoEntry({ id: "le-4", pod_id: "pod-1", source_ref: "CR-0999", campaign_id: "c1", gross_cents: 10001, status: "cleared",
    created_at: iso(40 * h), cleared_at: iso(38 * h) });
  const e5 = demoEntry({ id: "le-5", pod_id: "pod-1", source: "reversal", source_ref: "rev:le-4", campaign_id: "c1", gross_cents: -10001,
    reverses_id: "le-4", note: "Payout clawed back by Content Rewards", created_at: iso(6 * h) });
  const e6 = demoEntry({ id: "le-6", pod_id: "pod-2", source_ref: "CR-1101", campaign_id: "c1", gross_cents: 20000, created_at: iso(5 * h) });
  const ledger = [e3, e5, e6, e2, e1, e4];
  const ledgerEvents = [
    ...steps(e1, [e1.created_at, e1.cleared_at!, e1.approved_at!, e1.paid_at!]), ...steps(e2, [e2.created_at, e2.cleared_at!, e2.approved_at!]),
    ...steps(e3, [e3.created_at]), ...steps(e4, [e4.created_at, e4.cleared_at!]), ...steps(e5, [e5.created_at]), ...steps(e6, [e6.created_at]),
  ].sort((a, b) => b.at.localeCompare(a.at));
  return { ledger, ledgerEvents };
}

// Pods demo (D091): Pod 1 is Zo's roster; Pod 2 is a test pod with the two GTA-6-only streamers.
export const DEMO_PODS: Pod[] = [
  { id: "pod-1", slug: "pod-1", name: "Pod 1", status: "active" },
  { id: "pod-2", slug: "pod-2", name: "Pod 2", status: "trial" },
];
const POD_OF: Record<string, string> = { kaicenat: "pod-2", ishowspeed: "pod-2" };
/** Demo login: Zo (admin + Pod 1 owner), or `?as=pod-2` (Pod 2 owner) / `?as=pod-2&role=member` to preview a pod login. */
export function demoAccess(search = ""): Access {
  const q = new URLSearchParams(search);
  const as = DEMO_PODS.find((p) => p.slug === q.get("as"));
  if (as) return { admin: false, pods: [{ id: as.id, slug: as.slug, name: as.name, role: q.get("role") === "member" ? "member" : "owner" }] };
  return { admin: true, pods: [{ id: "pod-1", slug: "pod-1", name: "Pod 1", role: "owner" }] };
}

const AV: Record<string, string> = { lacy: "/demo/halo/av_lacy.jpg", jynxzi: "/demo/halo/av_jynxzi.jpg", stableronaldo: "/demo/halo/av_stableronaldo.jpg" };
const S = (id: string, slug: string, name: string, kick = false): Streamer => ({
  id, slug, display_name: name, twitch_login: kick ? null : slug, kick_slug: kick ? slug : null, avatar_url: AV[slug] ?? null,
  pod_id: POD_OF[slug] ?? "pod-1",
});

const HALO = ["full", "clip2", "clip1", "clip3", "clip4"];

export function demoSnapshot(now = Date.now()): Snapshot {
  const iso = (msAgo: number) => new Date(now - msAgo).toISOString();
  const min = 60_000;
  // Roster D069/D070: core five + GTA-6-only two.
  const streamers = [S("s-jynxzi", "jynxzi", "Jynxzi"), S("s-lacy", "lacy", "Lacy"), S("s-xqc", "xqc", "xQc"), S("s-adinross", "adinross", "Adin Ross", true),
    S("s-stableronaldo", "stableronaldo", "Stable Ronaldo"), S("s-kaicenat", "kaicenat", "Kai Cenat"),
    S("s-ishowspeed", "ishowspeed", "IShowSpeed")];
  const roster = { "twitch:jynxzi": "core", "twitch:lacy": "core", "twitch:xqc": "core", "kick:adinross": "core", "twitch:stableronaldo": "core",
    "twitch:kaicenat": "gta6_only", "twitch:ishowspeed": "gta6_only" } as const;
  let n = 0;
  const clip = (p: Partial<Clip> & { streamer_id: string; title: string }): Clip => {
    n += 1;
    const slug = p.streamer_id.slice(2);
    const media = ((n - 1) % 3) + 1;
    // Sample footage from the Halo design folder for the clips waiting in review.
    const halo = HALO[(n - 1) % HALO.length];
    const score = (p.score_10 ?? 7) * 10 + ((n * 7) % 9) - 4;
    const parts = { judged: { hook: Math.min(10, (score + 4) / 10), payoff: Math.min(10, (score - 2) / 10), standalone: 8, emotion: 7, share: 7 } };
    return {
      id: `demo-${n}`, job_id: `${slug}-${String(n).padStart(3, "0")}`, channel_key: `twitch:${slug}`, pod_id: POD_OF[slug] ?? "pod-1",
      state: "pending_review", hook: null, description: null, category: "gaming",
      confidence: 0.8, detector_score: 3.1, score_10: 7, hook_type: "reaction_peak",
      moment_at: iso(40 * min), duration_s: 34, storage_path: `/demo/halo/${halo}.mp4`,
      thumb_path: `/demo/halo/${halo}.jpg`, source_path: `/demo/source${media}.mp4`, fixing: null, qa: { passed: true, captions: "whisperX", size_mb: 21.4 },
      revision: 0, reviewed_at: null, created_at: iso(30 * min), ...p,
      judge: { score, parts, ...p.judge },
    };
  };
  const clips: Clip[] = [
    clip({ streamer_id: "s-lacy", title: "Lacy gets told \"you all die\" before the heist", score_10: 9, confidence: 0.88, detector_score: 4.1,
      duration_s: 40, hook: "IF ANYTHING GOES WRONG WE ALL DIE", hook_type: "reaction_peak", moment_at: iso(7 * min), created_at: iso(4 * min),
      judge: { why: "Chat spiked 4.1x in 6 s and the line lands without context.", hook_window: "0:00-0:02" } }),
    clip({ streamer_id: "s-lacy", title: "Lacy is locking in for the vault run", score_10: 8, confidence: 0.81, detector_score: 3.6,
      duration_s: 8, hook: "I'M LOCKING IN", hook_type: "play_peak", moment_at: iso(16 * min), created_at: iso(11 * min),
      judge: { why: "Callback the whole chat knows; short and clean.", hook_window: "0:00-0:03" } }),
    clip({ streamer_id: "s-lacy", title: "Reads the fan edit out loud", state: "published", score_10: 8, confidence: 0.79,
      duration_s: 22, reviewed_at: iso(5 * 3600_000), created_at: iso(6 * 3600_000) }),
    clip({ streamer_id: "s-lacy", title: "Speedrun the mission skip", state: "approved", score_10: 8, confidence: 0.8,
      duration_s: 29, reviewed_at: iso(50 * min), created_at: iso(80 * min) }),
    clip({ streamer_id: "s-lacy", title: "Calls his own bluff on stream", state: "published", score_10: 7, confidence: 0.74,
      duration_s: 24, reviewed_at: iso(26 * 3600_000), created_at: iso(27 * 3600_000) }),
    clip({ streamer_id: "s-jynxzi", title: "Final-circle 1v3 clutch", state: "scheduled", score_10: 8, confidence: 0.83,
      duration_s: 24, reviewed_at: iso(35 * min), created_at: iso(60 * min) }),
    clip({ streamer_id: "s-xqc", title: "xQc loses it at the 1v4 clutch", score_10: 9, confidence: 0.91,
      detector_score: 4.4, duration_s: 38, hook: "NO WAY HE CLUTCHED THAT", hook_type: "play_peak",
      moment_at: iso(9 * min), created_at: iso(6 * min),
      judge: { why: "Clean 1v4 with chat spike +340% inside 20 s; payoff lands at 0:31.", hook_window: "0:00-0:03" } }),
    clip({ streamer_id: "s-stableronaldo", title: "Clix calls the zone pull early", score_10: 8, confidence: 0.84,
      duration_s: 27, hook: "HE CALLED THE ZONE PULL", hook_type: "bold_claim", moment_at: iso(22 * min),
      created_at: iso(18 * min), judge: { why: "Bold call, then proof on screen 12 s later.", hook_window: "0:00-0:02" } }),
    clip({ streamer_id: "s-xqc", title: "Chat votes him out of his own squad", score_10: 8, confidence: 0.77,
      duration_s: 41, hook_type: "story_start", created_at: iso(25 * min),
      judge: { why: "Story setup works, ending is a bit soft.", hook_window: "0:00-0:04" } }),
    clip({ streamer_id: "s-stableronaldo", title: "Loadout roast goes too far", score_10: 7, confidence: 0.72,
      duration_s: 44, hook_type: "reaction_peak", created_at: iso(41 * min), revision: 1,
      judge: { why: "Funny, but the first 2 s are dead air.", hook_window: "0:02-0:05" } }),
    clip({ streamer_id: "s-kaicenat", title: "Kai reads the third party", score_10: 6, confidence: 0.66,
      duration_s: 52, hook_type: "play_peak", created_at: iso(140 * min),
      judge: { why: "Good read, slow build.", hook_window: "0:00-0:05" } }),
    clip({ streamer_id: "s-stableronaldo", title: "Storm rotate fail", score_10: 4, confidence: 0.58, duration_s: 22,
      hook_type: "none", created_at: iso(55 * min), judge: { why: "Weak hook, no clear payoff." }, pod_id: null }),
    clip({ streamer_id: "s-stableronaldo", title: "Chat roasts the loadout", state: "approved", score_10: 8, confidence: 0.8,
      reviewed_at: iso(14 * min), created_at: iso(70 * min) }),
    clip({ streamer_id: "s-xqc", title: "xQc rage quits then requeues", state: "published", score_10: 8,
      confidence: 0.82, reviewed_at: iso(30 * min), created_at: iso(90 * min) }),
  ];
  const candidates: Candidate[] = [];
  for (const [key, seed] of [["twitch:lacy", 4], ["twitch:xqc", 3], ["twitch:stableronaldo", 7], ["twitch:kaicenat", 5]] as const) {
    for (let i = 0; i < 72; i += 1) {
      const wave = Math.abs(Math.sin((i + seed) * 0.7) * 1.2 + Math.sin((i * seed) * 0.13));
      const spike = i === 66 || i === 41 || i === 18 ? 2.6 : 0;
      candidates.push({ channel_key: key, pod_id: POD_OF[key.split(":")[1]] ?? "pod-1", moment_at: iso((72 - i) * 2.5 * min), score: +(0.6 + wave + spike).toFixed(2),
        outcome: spike ? "kept" : "dropped" });
    }
  }
  // Long-form TikTok (D079-D082): one in review, one approved and posted.
  clips.push(
    clip({ streamer_id: "s-lacy", title: "Lacy cannot stop driving off bridges", score_10: 9, duration_s: 72,
      category: "longform", hook_type: "story_start", hook: "Lacy found a new bridge", moment_at: iso(80 * min),
      created_at: iso(4 * min), job_id: "long-demo1", qa: { passed: true, coverage: 0.44 },
      judge: { why: "Narrated recap of 3 moments from today's stream. Narration 44% of runtime." } }),
    clip({ streamer_id: "s-jynxzi", title: "Jynxzi's worst ranked night, retold", score_10: 8, duration_s: 68,
      category: "longform", state: "approved", reviewed_at: iso(70 * min), job_id: "long-demo2" }),
  );
  const longform: LongformVideo[] = [
    { id: "demo1", clip_id: clips[clips.length - 2].id, channel: "zwoclipp", format: "recap", pacing: "short",
      caption_style: "A", voice: "ai", layout: "switch", runtime_s: 72, coverage: 0.44, tiktok_url: null, posted_at: null, notice: "none" },
    { id: "demo2", clip_id: clips[clips.length - 1].id, channel: "zwoclipp", format: "topn", pacing: "short",
      caption_style: "B", voice: "ai", layout: "switch", runtime_s: 68, coverage: 0.42, tiktok_url: null, posted_at: null, notice: "none" },
  ];
  // Live numbers as /api/live would write them (Twitch Helix / Kick / YouTube / X); TikTok typed in by hand.
  const ls = (key: string, p: Partial<LiveStat>): LiveStat => ({
    key, kind: "streamer", platform: key.startsWith("kick") ? "kick" : "twitch", is_live: false, viewers: null, followers: null,
    views: null, posts: null, title: null, game: null, started_at: null, avatar_url: null, updated_at: iso(3_000), ...p,
  });
  const live: LiveStat[] = [
    ls("twitch:lacy", { is_live: true, viewers: 31240, game: "Grand Theft Auto VI", title: "GTA 6 day 3 · new map", started_at: iso(134 * min) }),
    ls("twitch:stableronaldo", { is_live: true, viewers: 21800, game: "Grand Theft Auto VI", title: "chaos lobby", started_at: iso(48 * min) }),
    ls("twitch:xqc", { is_live: true, viewers: 61400, game: "Grand Theft Auto VI", started_at: iso(182 * min) }),
    ls("twitch:kaicenat", { is_live: true, viewers: 88900, game: "Grand Theft Auto VI", started_at: iso(61 * min) }),
    ls("twitch:jynxzi", { is_live: false }), ls("kick:adinross", { is_live: false }), ls("twitch:ishowspeed", { is_live: false }),
    ls("youtube:own", { kind: "own", platform: "youtube", followers: 18420, views: 2_910_000, posts: 212, title: "Zwoclipp" }),
    ls("x:own", { kind: "own", platform: "x", followers: 6310, posts: 488, title: "zwoclipp" }),
    ls("tiktok:own", { kind: "own", platform: "tiktok", followers: 24100, views: 3_420_000, posts: 96, updated_at: iso(9 * 3600_000) }),
  ];
  // 30 days of history, one point a day, smooth growth with a little noise (seeded, so screenshots are stable).
  let seed = 7;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const history: StatPoint[] = [];
  const grow = (key: string, metric: string, from: number, to: number) => {
    for (let d = 29; d >= 0; d -= 1) {
      const f = (29 - d) / 29;
      history.push({ key, metric, value: Math.round(from + (to - from) * f * f + (to - from) * 0.04 * (rnd() - 0.5)), at: iso(d * 86400_000 + 3600_000) });
    }
  };
  grow("youtube:own", "views", 1_120_000, 2_910_000); grow("youtube:own", "followers", 9100, 18420);
  grow("x:own", "followers", 4200, 6310); grow("tiktok:own", "views", 1_300_000, 3_420_000); grow("tiktok:own", "followers", 11800, 24100);
  for (let i = 0; i < 14; i += 1) history.push({ key: "twitch:lacy", metric: "viewers", value: Math.round(24000 + 7000 * Math.sin(i / 2.2) + 3000 * rnd()), at: iso((14 - i) * 10 * min) });
  const publications: Publication[] = [
    { id: "p1", clip_id: "demo-3", status: "posted", url: "https://youtube.com/shorts/demo1", posted_at: iso(5 * 3600_000), created_at: iso(5 * 3600_000), platform: "youtube", label: "Shorts: main" },
    { id: "p2", clip_id: "demo-3", status: "posted", url: "https://x.com/zwoclipp/status/1", posted_at: iso(5 * 3600_000), created_at: iso(5 * 3600_000), platform: "x", label: "X: main" },
    { id: "p3", clip_id: "demo-6", status: "pending", url: null, posted_at: null, created_at: iso(30 * min), platform: "youtube", label: "Shorts: main" },
    { id: "p4", clip_id: "demo-4", status: "posting", url: null, posted_at: null, created_at: iso(2 * min), platform: "x", label: "X: main" },
  ];
  const campaigns: Campaign[] = [
    { id: "c1", title: "GTA 6 launch week clips", status: "active", source_url: null, streamer_slugs: ["lacy", "kaicenat", "ishowspeed"],
      platforms: ["youtube", "x", "tiktok"], cpm_usd: 1.5, cap_usd: 2500, deadline: iso(-6 * 86400_000), score: 8.6, recommendation: "pursue: Lacy fits, GTA 6 is our priority", created_at: iso(3 * 86400_000) },
    { id: "c2", title: "Jynxzi R6 ranked highlights", status: "active", source_url: null, streamer_slugs: ["jynxzi"],
      platforms: ["youtube", "tiktok"], cpm_usd: 1.0, cap_usd: 800, deadline: iso(-12 * 86400_000), score: 7.1, recommendation: "pursue: steady volume", created_at: iso(5 * 86400_000) },
    { id: "c3", title: "Energy drink brand reacts", status: "avoid", source_url: null, streamer_slugs: ["adinross"],
      platforms: ["x"], cpm_usd: 0.4, cap_usd: 300, deadline: iso(-2 * 86400_000), score: 3.2, recommendation: "avoid: low CPM, X only", created_at: iso(86400_000) },
  ];
  const brains: BrainWeights[] = [
    { streamer_id: "s-lacy", weights: { chat_spike: 72, voice_peak: 58, chat_words: 81, viewer_clips: 34, approved_match: 66 }, words: ["CLIP", "NO WAY", "LACY"], updated_at: iso(86400_000) },
    { streamer_id: "s-jynxzi", weights: { chat_spike: 64, voice_peak: 77, chat_words: 52, viewer_clips: 41, approved_match: 58 }, words: ["JYNXZI", "W"], updated_at: iso(2 * 86400_000) },
  ];
  // Pod home (Phase 3): one suggested campaign per pod, two posts stuck under 20 plays at ~1 h.
  const podCampaigns: PodCampaign[] = [
    { pod_id: "pod-1", campaign_id: "c1", status: "joined", scout: {}, decided_at: iso(2 * 86400_000), created_at: iso(3 * 86400_000) },
    { pod_id: "pod-1", campaign_id: "c2", status: "suggested", scout: { reason: "Jynxzi is in this pod; $1.00 CPM clears the floor" }, decided_at: null, created_at: iso(5 * 3600_000) },
    { pod_id: "pod-2", campaign_id: "c1", status: "suggested", scout: { reason: "Kai Cenat and IShowSpeed are named" }, decided_at: null, created_at: iso(3 * 3600_000) },
  ];
  const postStats: PostStat[] = [
    { clip_id: "demo-3", platform: "youtube", read_at: iso(4 * 3600_000), hours_since_post: 1, plays: 1450 },
    { clip_id: "demo-3", platform: "x", read_at: iso(4 * 3600_000), hours_since_post: 1, plays: 12 },
    { clip_id: "demo-14", platform: "youtube", read_at: iso(20 * min), hours_since_post: 1.1, plays: 8 },
  ];
  const ledgerData = demoLedger(iso);
  return {
    pods: DEMO_PODS, podCampaigns, postStats, ...ledgerData, statements: demoStatements(ledgerData.ledger),
    live, history, publications, campaigns, brains,
    streamers,
    clips,
    submissions: [{
      id: "demo-sub-1", publication_id: "demo-pub-1", campaign_id: null,
      post_url: "https://x.com/clipp/status/1859000000000000000",
      posted_at: iso(11 * min + 18_000), deadline_at: new Date(now + 18 * min + 42_000).toISOString(),
      submitted_at: null, status: "open", seconds_left: 18 * 60 + 42,
    }],
    heartbeat: {
      worker_id: "daddys", seen_at: iso(4_000),
      status: { version: "0.3.0", awake: true, live: ["twitch:lacy", "twitch:xqc", "twitch:stableronaldo", "twitch:kaicenat"],
        capturing: ["twitch:lacy", "twitch:xqc", "twitch:stableronaldo", "twitch:kaicenat"], queue: { captured: 1, transcribed: 1, judged: 1, rendered: 1 },
        gpu: { name: "RTX 5060", util: 62, mem_used_gb: 5.1, mem_total_gb: 8 }, disk: { used_pct: 38, free_gb: 610 },
        live_since: { "twitch:lacy": iso(134 * min), "twitch:xqc": iso(182 * min), "twitch:stableronaldo": iso(48 * min), "twitch:kaicenat": iso(61 * min) },
        viewers: { "twitch:lacy": 31240, "twitch:xqc": 61400, "twitch:stableronaldo": 21800, "twitch:kaicenat": 88900 },
        games: { "twitch:lacy": "Grand Theft Auto VI", "twitch:xqc": "Grand Theft Auto VI", "twitch:stableronaldo": "Grand Theft Auto VI",
          "twitch:kaicenat": "Grand Theft Auto VI" },
        roster },
    },
    destinations: [
      { id: "demo-yt", platform: "youtube", label: "Shorts: main", active: true, streamer_id: null },
      { id: "demo-x", platform: "x", label: "X: main", active: true, streamer_id: null },
    ],
    spendDays: Array.from({ length: 14 }, (_, i) => ({ day: new Date(now - (13 - i) * 86400_000).toISOString().slice(0, 10),
      usd: +(2.4 + 0.18 * i + 0.9 * Math.abs(Math.sin(i * 1.7))).toFixed(2) })),
    candidates,
    spend: [{ kind: "grok", usd: 31.2 }, { kind: "x_post", usd: 38.0 }, { kind: "storage", usd: 4.8 }],
    revisions: [{ id: "demo-rev-1", clip_id: "demo-4", kind: "other", note: "cut the first two seconds",
      created_at: iso(48 * min), resolved_at: iso(43 * min) }],
    rules: [{ id: "demo-rule-1", key: "zoom_style", value: "smooth", label: "Smooth camera: eased zooms only on big moments",
      note: "the zoom in and out is way too sharp, make it smoother", clip_id: "demo-4", active: true,
      fixed_count: 2, created_at: iso(47 * min) }],
    longform,
    results: [
      { format: "recap", pacing: "short", caption_style: "A", voice: "ai", layout: "switch", posts: 6, notices: 0,
        avg_watch_s: 31.2, hold_5s_pct: 71.0, follows_per_1k: 4.8, rpm_usd: null },
      { format: "topn", pacing: "short", caption_style: "A", voice: "ai", layout: "switch", posts: 6, notices: 1,
        avg_watch_s: 27.5, hold_5s_pct: 66.0, follows_per_1k: 3.1, rpm_usd: null },
    ],
  };
}

