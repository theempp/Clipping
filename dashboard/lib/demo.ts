// Sample day for demo mode (D057). Times are relative to page load so the
// countdown and "live for" clocks move. Nothing here touches the network.
import type { Candidate, Clip, LongformVideo, Snapshot, Streamer } from "./types.ts";

const S = (id: string, slug: string, name: string, kick = false): Streamer => ({
  id, slug, display_name: name, twitch_login: kick ? null : slug, kick_slug: kick ? slug : null, avatar_url: null,
});

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
    return {
      id: `demo-${n}`, job_id: `${slug}-${String(n).padStart(3, "0")}`, channel_key: `twitch:${slug}`,
      state: "pending_review", hook: null, description: null, category: "gaming",
      confidence: 0.8, detector_score: 3.1, score_10: 7, hook_type: "reaction_peak",
      moment_at: iso(40 * min), duration_s: 34, storage_path: `/demo/clip${media}.mp4`,
      thumb_path: `/demo/thumb${media}.jpg`, source_path: `/demo/source${media}.mp4`, fixing: null, qa: { passed: true, captions: "whisperX", size_mb: 21.4 },
      judge: {}, revision: 0, reviewed_at: null, created_at: iso(30 * min), ...p,
    };
  };
  const clips: Clip[] = [
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
      hook_type: "none", created_at: iso(55 * min), judge: { why: "Weak hook, no clear payoff." } }),
    clip({ streamer_id: "s-stableronaldo", title: "Chat roasts the loadout", state: "approved", score_10: 8, confidence: 0.8,
      reviewed_at: iso(14 * min), created_at: iso(70 * min) }),
    clip({ streamer_id: "s-xqc", title: "xQc rage quits then requeues", state: "published", score_10: 8,
      confidence: 0.82, reviewed_at: iso(30 * min), created_at: iso(90 * min) }),
  ];
  const candidates: Candidate[] = [];
  for (const [key, seed] of [["twitch:xqc", 3], ["twitch:stableronaldo", 7], ["twitch:kaicenat", 5]] as const) {
    for (let i = 0; i < 72; i += 1) {
      const wave = Math.abs(Math.sin((i + seed) * 0.7) * 1.2 + Math.sin((i * seed) * 0.13));
      const spike = i === 66 || i === 41 || i === 18 ? 2.6 : 0;
      candidates.push({ channel_key: key, moment_at: iso((72 - i) * 2.5 * min), score: +(0.6 + wave + spike).toFixed(2),
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
  return {
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
      status: { version: "0.3.0", awake: true, live: ["twitch:xqc", "twitch:stableronaldo", "twitch:kaicenat"],
        capturing: ["twitch:xqc", "twitch:stableronaldo", "twitch:kaicenat"], queue: { captured: 1, judged: 1, rendered: 1 },
        gpu: { name: "RTX 5060", util: 62, mem_used_gb: 5.1, mem_total_gb: 8 },
        live_since: { "twitch:xqc": iso(134 * min), "twitch:stableronaldo": iso(182 * min), "twitch:kaicenat": iso(61 * min) },
        viewers: { "twitch:xqc": 61400, "twitch:stableronaldo": 21800, "twitch:kaicenat": 88900 },
        games: { "twitch:xqc": "Grand Theft Auto VI", "twitch:stableronaldo": "Grand Theft Auto VI",
          "twitch:kaicenat": "Grand Theft Auto VI" },
        roster },
    },
    control: { awake: true, updated_at: iso(134 * min) },
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

