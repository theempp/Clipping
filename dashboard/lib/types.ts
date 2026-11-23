export type ClipState =
  | "qa_passed" | "pending_review" | "approved" | "revise"
  | "rejected" | "scheduled" | "published" | "failed";

export type Streamer = {
  id: string;
  slug: string;
  display_name: string;
  twitch_login: string | null;
  kick_slug: string | null;
  avatar_url: string | null;
  /** Pods migration (20261124000000): the pod this streamer clips for. */
  pod_id?: string | null;
};

export type Clip = {
  id: string;
  job_id: string;
  streamer_id: string | null;
  channel_key: string;
  /** Pod tag (pods migration). Null = untagged; only the admin reviews those (D102). */
  pod_id?: string | null;
  state: ClipState;
  title: string | null;
  hook: string | null;
  description: string | null;
  category: string | null;
  confidence: number | null;
  detector_score: number | null;
  score_10: number | null;
  hook_type: string | null;
  moment_at: string;
  duration_s: number | null;
  storage_path: string | null;
  thumb_path: string | null;
  /** The untouched 16:9 stream window, for before/after (D077). Older clips have none. */
  source_path?: string | null;
  /** Set while the PC re-edits this clip to meet a learned rule; hidden from review meanwhile (D078). */
  fixing?: { rules: string[]; since: string } | null;
  /** Set by the PC when a revision's re-render failed QA; the clip waits in "revise" for Zo. */
  revise_failed?: { rev: number; reason: string; at: string; revisions: string[] } | null;
  qa: Record<string, unknown>;
  /** Render manifest from the PC; `peaks` is the measured audio waveform (0-100). */
  manifest?: Record<string, unknown>;
  judge: Record<string, unknown>;
  revision: number;
  reviewed_at: string | null;
  created_at: string;
};

export type Submission = {
  id: string;
  publication_id: string;
  campaign_id: string | null;
  post_url: string;
  posted_at: string;
  deadline_at: string;
  submitted_at: string | null;
  status: "open" | "submitted" | "missed";
  seconds_left: number;
};

export type Heartbeat = {
  worker_id: string;
  seen_at: string;
  status: {
    version?: string;
    awake?: boolean;
    live?: string[];
    capturing?: string[];
    queue?: Record<string, number>;
    live_since?: Record<string, string>;
    viewers?: Record<string, number>;
    games?: Record<string, string>;                      // channel key -> current category
    roster?: Record<string, "core" | "gta6_only">;       // active roster (D069); absent on older workers
    gpu?: { name?: string; util?: number; mem_used_gb?: number; mem_total_gb?: number };
    disk?: { used_pct?: number; free_gb?: number };                 // optional; older workers omit it
  };
};

export type Control = { awake: boolean; updated_at: string };

export type Candidate = { channel_key: string; moment_at: string; score: number; outcome: string; pod_id?: string | null };

export type Spend = { kind: string; usd: number };

export type Revision = { id: string; clip_id: string; kind: string; note: string; created_at: string; resolved_at: string | null };

/** Long-form TikTok video (D079-D082): test tags, manual post, eligibility notice. */
export type LongformVideo = {
  id: string;
  clip_id: string | null;
  channel: string;
  format: "recap" | "topn" | "explainer" | "extended";
  pacing: "short" | "long";
  caption_style: "A" | "B";
  voice: "ai" | "zo";
  layout: "switch" | "stacked";
  runtime_s: number;
  coverage: number | null;
  tiktok_url: string | null;
  posted_at: string | null;
  notice: "none" | "ineligible" | "unoriginal";
};

export type TiktokStats = {
  views?: number; for_you_views?: number; qualified_views?: number; avg_watch_s?: number;
  watched_full_pct?: number; hold_5s_pct?: number; follows?: number; search_views_pct?: number; rewards_usd?: number;
};

export type LongformResult = {
  format: string; pacing: string; caption_style: string; voice: string; layout: string;
  posts: number; notices: number; avg_watch_s: number | null; hold_5s_pct: number | null;
  follows_per_1k: number | null; rpm_usd: number | null;
};

/** A standing edit learned from one of Zo's revision notes (D078). */
export type EditRule = {
  id: string; key: string; value: unknown; label: string; note: string;
  clip_id: string | null; active: boolean; fixed_count: number; created_at: string;
};

/** One live number row (migration 20261123000000_live_stats): a streamer channel or one of Zo's own channels.
 *  Written server-side by /api/live (Twitch Helix, Kick, YouTube, X) and pushed to the UI by Supabase Realtime. */
export type LiveStat = {
  key: string;                 // twitch:lacy · kick:adinross · youtube:own · x:own · tiktok:own
  kind: "streamer" | "own";
  platform: "twitch" | "kick" | "youtube" | "x" | "tiktok";
  is_live: boolean | null;
  viewers: number | null;
  followers: number | null;
  views: number | null;
  posts: number | null;
  title: string | null;
  game: string | null;
  started_at: string | null;
  avatar_url: string | null;
  updated_at: string;
};

/** A point on a growth chart: one metric of one live-stat key at one time. */
export type StatPoint = { key: string; metric: string; value: number; at: string };

export type Publication = {
  id: string; clip_id: string; status: "pending" | "posting" | "posted" | "failed";
  url: string | null; posted_at: string | null; created_at: string; platform: string | null; label: string | null;
};

export type Campaign = {
  id: string; title: string; status: "draft" | "active" | "paused" | "ended" | "avoid";
  source_url: string | null; streamer_slugs: string[]; platforms: string[];
  cpm_usd: number | null; cap_usd: number | null; deadline: string | null;
  score: number | null; recommendation: string | null; created_at: string;
};

/** What the detector weighs for one streamer (Streamer Brain, D089). 0-100 each. */
export type BrainWeights = {
  streamer_id: string;
  weights: Record<string, number>;
  words: string[];
  updated_at: string;
};

export type Snapshot = {
  streamers: Streamer[];
  clips: Clip[];
  submissions: Submission[];
  heartbeat: Heartbeat | null;
  control: Control;
  candidates: Candidate[];
  spend: Spend[];
  revisions: Revision[];
  longform: LongformVideo[];
  results: LongformResult[];
  rules: EditRule[];
  live: LiveStat[];
  history: StatPoint[];
  publications: Publication[];
  campaigns: Campaign[];
  brains: BrainWeights[];
  /** Pods (NEXT_PUBLIC_CLIPP_PODS=1). Empty while the flag is off. */
  pods: Pod[];
  podCampaigns: PodCampaign[];
  /** Early post_stats readings (<= 2.5 h), enough for the stuck-post flag. */
  postStats: PostStat[];
  statements: PodStatement[];
  /** Ledger (Phase 4): itemized entries and their append-only audit rows. */
  ledger: LedgerEntry[];
  ledgerEvents: LedgerEvent[];
};

/** Manual editor output (trim + crop + headline + captions), sent as a revision payload. */
export type EditPlan = {
  trim_in: number; trim_out: number; crop_x: number; zoom: number;
  headline: string; caption_style: "words" | "line"; splits: number[];
  /** Words the captions highlight (worker `emphasis_words`). */
  emphasis_words: string[];
  /** Start times of the pieces between splits that Zo dropped; the PC cuts them out. */
  drop?: number[];
};

export type ReviewAction = "approve" | "revise" | "reject";

/** Pods (D091-D109, migration 20261124000000_pods). */
export type PodRole = "owner" | "member";
export type Pod = { id: string; slug: string; name: string; status: "trial" | "active" | "ended" };
/** One row of my_access().pods: a pod the signed-in user belongs to. */
export type PodAccess = { id: string; slug: string; name: string; role: PodRole };
/** my_access(): admin sees every pod; pods = the user's own memberships. */
export type Access = { admin: boolean; pods: PodAccess[] };
/** Campaign participation per pod; the per-pod scout writes `suggested` rows (D106: the pod owner decides). */
export type PodCampaign = {
  pod_id: string; campaign_id: string; status: "suggested" | "joined" | "declined" | "left";
  scout: Record<string, unknown>; decided_at: string | null; created_at: string;
};
/** One stats reading of one post (migration 20261122230000). */
export type PostStat = { clip_id: string; platform: "youtube" | "x" | "tiktok"; read_at: string; hours_since_post: number; plays: number | null };
/** pod_statements view: one pod, one month. Money is cents, computed in the database. */
export type PodStatement = {
  pod_id: string; month: string; entries: number; gross_cents: number; agency_cut_cents: number; pod_net_cents: number;
  pending_net_cents: number; owed_net_cents: number; paid_net_cents: number;
};
export type LedgerStatus = "pending" | "cleared" | "approved" | "paid";
/** ledger_entries row. agency_cut_cents / pod_net_cents are generated columns: never computed in the UI. */
export type LedgerEntry = {
  id: string; pod_id: string; source: "campaign" | "reversal"; source_ref: string; campaign_id: string | null;
  gross_cents: number; agency_rate: number; agency_cut_cents: number; pod_net_cents: number;
  status: LedgerStatus; note: string | null; reverses_id: string | null;
  cleared_at: string | null; approved_at: string | null; paid_at: string | null; paid_ref: string | null; created_at: string;
};
/** ledger_events row (trigger-written, append-only). */
export type LedgerEvent = {
  id: number; entry_id: string; pod_id: string; op: "insert" | "update";
  from_status: LedgerStatus | null; to_status: LedgerStatus; actor: string; actor_id: string | null;
  row_after: Record<string, unknown>; at: string;
};
