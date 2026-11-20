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
    gpu?: { name?: string; util?: number; mem_used_gb?: number; mem_total_gb?: number };
  };
};

export type Control = { awake: boolean; updated_at: string };

export type Candidate = { channel_key: string; moment_at: string; score: number; outcome: string };

export type Spend = { kind: string; usd: number };

export type Revision = { id: string; clip_id: string; kind: string; note: string; created_at: string; resolved_at: string | null };

export type Snapshot = {
  streamers: Streamer[];
  clips: Clip[];
  submissions: Submission[];
  heartbeat: Heartbeat | null;
  control: Control;
  candidates: Candidate[];
  spend: Spend[];
  revisions: Revision[];
};

export type ReviewAction = "approve" | "revise" | "reject";
