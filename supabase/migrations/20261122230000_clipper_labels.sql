-- Clipper wiring, Phase 0 (D089, docs/clipper-review/wiring-plan.md step 4).
-- Learning labels per streamer, platform stats at 2 h / 24 h / 72 h, brain snapshots
-- for rollback, and CLIP THAT requests. Worker writes with the service role; zo reads, and enters manual stats.
-- Nothing reads these tables until the matching worker flags are switched on.

create table public.clip_labels (
  id uuid primary key default gen_random_uuid(),
  clip_id uuid references public.clips(id) on delete cascade,  -- null: moment with no clip yet (CLIP THAT, viewer clip we missed)
  job_id text,
  streamer text not null,                                        -- streamers.slug; one brain per streamer
  signal text not null check (signal in ('approved', 'approved_revised', 'rejected', 'viewer_clip',
                                         'beat_median', 'under_median', 'missed_moment', 'judge_dropped')),
  weight real not null check (weight between -2 and 2 and weight <> 0),  -- + positive, - negative
  moment_at timestamptz,
  reason text,
  created_at timestamptz not null default now(),
  unique (streamer, job_id, signal)
);
create index clip_labels_streamer_idx on public.clip_labels(streamer, created_at desc);

create table public.post_stats (
  id uuid primary key default gen_random_uuid(),
  clip_id uuid not null references public.clips(id) on delete cascade,
  platform text not null check (platform in ('youtube', 'x', 'tiktok')),
  read_at timestamptz not null default now(),
  hours_since_post real not null check (hours_since_post >= 0),
  plays int check (plays >= 0),
  likes int check (likes >= 0),
  shares int check (shares >= 0),
  comments int check (comments >= 0),
  saves int check (saves >= 0),
  follows int check (follows >= 0),
  source text not null default 'api' check (source in ('api', 'manual')),
  unique (clip_id, platform, read_at)
);
create index post_stats_clip_idx on public.post_stats(clip_id, platform, hours_since_post);

create table public.brain_versions (
  streamer text not null,
  version int not null check (version >= 0),
  json jsonb not null,
  created_at timestamptz not null default now(),
  primary key (streamer, version)
);

alter table public.clip_labels enable row level security;
alter table public.post_stats enable row level security;
alter table public.brain_versions enable row level security;
create policy owner_read on public.clip_labels for select to authenticated using (public.is_owner());
create policy owner_read on public.post_stats for select to authenticated using (public.is_owner());
create policy owner_read on public.brain_versions for select to authenticated using (public.is_owner());
-- TikTok stats are typed in by zo until an API exists (D074): manual rows only.
create policy owner_insert_manual on public.post_stats for insert to authenticated
  with check (public.is_owner() and source = 'manual');

-- CLIP THAT (wiring-plan step 8): zo asks for the last 40 s of a live stream. The worker
-- polls open requests (features.clip_that), cuts the window and marks the request done.
create table public.clip_requests (
  id uuid primary key default gen_random_uuid(),
  streamer text not null,
  requested_at timestamptz not null default now(),
  seconds smallint not null default 40 check (seconds between 10 and 90),
  source text not null default 'dashboard' check (source in ('dashboard', 'discord')),
  status text not null default 'open' check (status in ('open', 'done', 'failed')),
  job_id text,
  detail text
);
create index clip_requests_open_idx on public.clip_requests(status, requested_at);
alter table public.clip_requests enable row level security;
create policy owner_read on public.clip_requests for select to authenticated using (public.is_owner());

create or replace function public.request_clip(p_streamer text, p_seconds int default 40)
returns public.clip_requests language plpgsql security definer set search_path = public as $$
declare r public.clip_requests;
begin
  if not public.is_owner() then raise exception 'not allowed'; end if;
  insert into public.clip_requests(streamer, seconds) values (p_streamer, p_seconds) returning * into r;
  return r;
end $$;
revoke execute on function public.request_clip(text, int) from public, anon;
grant execute on function public.request_clip(text, int) to authenticated;
