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
};

export type Clip = {
  id: string;
  job_id: string;
  streamer_id: string | null;
  channel_key: string;
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
  qa: Record<string, unknown>;
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
  };
};

export type Control = { awake: boolean; updated_at: string };

export type Candidate = { channel_key: string; moment_at: string; score: number; outcome: string };

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
};

export type ReviewAction = "approve" | "revise" | "reject";
