-- Paste-a-link clip creation (D115, pending zo). zo pastes a Twitch/Kick/YouTube/X link in the
-- dashboard; the PC downloads it, runs detect -> Grok judge -> render -> QA, and every clip lands
-- in the normal review queue as pending_review. Nothing posts from here: the review gate and the
-- per-batch publish approval are unchanged.

-- Canonical key for duplicate checks: platform + kind + id. Null = unsupported link.
-- Same rules as dashboard/lib/links.ts and worker/src/clipworker/links.py (tests keep them in step).
create or replace function public.link_key(p_url text) returns text
language plpgsql immutable set search_path = public as $$
declare u text; host text; path text; q text; m text[];
begin
  u := btrim(coalesce(p_url, ''));
  if u !~* '^https://' or length(u) > 500 then return null; end if;
  u := regexp_replace(u, '^https://', '', 'i');
  host := lower(split_part(split_part(u, '/', 1), '?', 1));
  if host like '%@%' or host like '%:%' then return null; end if;   -- no userinfo, no port
  host := regexp_replace(host, '^(www|m|mobile)\.', '');
  path := substr(u, length(split_part(u, '/', 1)) + 1);
  q := coalesce(substring(path from '\?(.*)$'), '');
  path := split_part(split_part(path, '?', 1), '#', 1);
  if host = 'twitch.tv' then
    m := regexp_match(path, '^/videos/([0-9]+)/?$');
    if m is not null then return 'twitch:vod:' || m[1]; end if;
    m := regexp_match(path, '^/[A-Za-z0-9_]+/clip/([A-Za-z0-9_-]+)/?$');
    if m is not null then return 'twitch:clip:' || m[1]; end if;
  elsif host = 'clips.twitch.tv' then
    m := regexp_match(path, '^/([A-Za-z0-9_-]+)/?$');
    if m is not null then return 'twitch:clip:' || m[1]; end if;
  elsif host = 'kick.com' then
    m := regexp_match(path, '^/(?:[A-Za-z0-9_-]+/)?videos?/([0-9a-fA-F-]{36})/?$');
    if m is not null then return 'kick:vod:' || lower(m[1]); end if;
    m := regexp_match(path, '^/[A-Za-z0-9_-]+/clips/([A-Za-z0-9_]+)/?$');
    if m is not null then return 'kick:clip:' || m[1]; end if;
    m := regexp_match(q, '(?:^|&)clip=([A-Za-z0-9_]+)');
    if m is not null and path ~ '^/[A-Za-z0-9_-]+/?$' then return 'kick:clip:' || m[1]; end if;
  elsif host in ('youtube.com', 'youtu.be') then
    m := regexp_match(path, '^/([A-Za-z0-9_-]{11})/?$');
    if host = 'youtu.be' and m is not null then return 'youtube:' || m[1]; end if;
    m := regexp_match(path, '^/(?:live|shorts)/([A-Za-z0-9_-]{11})/?$');
    if m is not null then return 'youtube:' || m[1]; end if;
    if path = '/watch' then
      m := regexp_match(q, '(?:^|&)v=([A-Za-z0-9_-]{11})(?:&|$)');
      if m is not null then return 'youtube:' || m[1]; end if;
    end if;
  elsif host in ('x.com', 'twitter.com') then
    m := regexp_match(path, '^/[A-Za-z0-9_]+/status/([0-9]+)(?:/video/[0-9])?/?$');
    if m is not null then return 'x:' || m[1]; end if;
  end if;
  return null;
end $$;

create table public.link_jobs (
  id uuid primary key default gen_random_uuid(),
  url text not null check (length(url) <= 500),
  url_key text not null,
  platform text not null check (platform in ('twitch', 'kick', 'youtube', 'x')),
  streamer text,                         -- streamers.slug; null = the PC detects it from the link
  start_s int check (start_s >= 0),      -- optional range inside the source (seconds)
  end_s int,
  max_clips smallint not null default 6 check (max_clips between 1 and 20),
  full_frame boolean not null default false,   -- IRL / full-cam source: face-tracked full frame
  status text not null default 'queued'
    check (status in ('queued', 'fetching', 'detecting', 'clipping', 'done', 'failed', 'canceled')),
  detail text,                           -- progress line or failure reason, shown in the dashboard
  source_title text,
  duration_s int,
  chat boolean,                          -- true = chat replay used for detection; false = audio only
  candidates int not null default 0,
  judged int not null default 0,
  clips int not null default 0,          -- reached pending_review
  dropped int not null default 0,
  est_usd numeric(8,4) not null default 0,
  cost_usd numeric(8,4) not null default 0,
  job_ids text[] not null default '{}',
  requested_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  updated_at timestamptz not null default now(),
  check (end_s is null or end_s > coalesce(start_s, 0)),
  check (end_s is null or end_s - coalesce(start_s, 0) <= 8 * 3600)
);
-- One live request per link + range. Failed and canceled ones can be pasted again.
create unique index link_jobs_once on public.link_jobs(url_key, coalesce(start_s, -1), coalesce(end_s, -1))
  where status not in ('failed', 'canceled');
create index link_jobs_queue on public.link_jobs(status, requested_at);
alter table public.link_jobs enable row level security;
create policy owner_read on public.link_jobs for select to authenticated using (public.is_owner());

create or replace function public.link_jobs_touch() returns trigger language plpgsql as $$
begin new.updated_at := now(); return new; end $$;
create trigger link_jobs_touch before update on public.link_jobs
  for each row execute function public.link_jobs_touch();

-- Shared body; callers check who is asking. Returns {"job": row, "duplicate": bool};
-- a duplicate returns the existing request instead of making a second one.
create or replace function public._request_link(p_url text, p_streamer text, p_start int, p_end int,
  p_max int, p_full_frame boolean)
returns jsonb language plpgsql security definer set search_path = public as $$
declare k text; r public.link_jobs; v_slug text;
begin
  k := public.link_key(p_url);
  if k is null then raise exception 'unsupported link: paste a Twitch, Kick, YouTube or X video link'; end if;
  v_slug := nullif(btrim(coalesce(p_streamer, '')), '');
  if v_slug is not null and not exists (select 1 from public.streamers s where s.slug = v_slug) then
    raise exception 'unknown streamer %', v_slug;
  end if;
  select * into r from public.link_jobs
   where url_key = k and coalesce(start_s, -1) = coalesce(p_start, -1) and coalesce(end_s, -1) = coalesce(p_end, -1)
     and status not in ('failed', 'canceled');
  if found then return jsonb_build_object('job', to_jsonb(r), 'duplicate', true); end if;
  insert into public.link_jobs(url, url_key, platform, streamer, start_s, end_s, max_clips, full_frame, est_usd)
  values (btrim(p_url), k, split_part(k, ':', 1), v_slug, p_start, p_end, coalesce(p_max, 6),
          coalesce(p_full_frame, false), round(coalesce(p_max, 6) * 0.0025, 4))
  returning * into r;
  return jsonb_build_object('job', to_jsonb(r), 'duplicate', false);
end $$;

-- Dashboard paste: owner only.
create or replace function public.request_link_clips(p_url text, p_streamer text default null,
  p_start int default null, p_end int default null, p_max int default 6, p_full_frame boolean default false)
returns jsonb language plpgsql security definer set search_path = public as $$
begin
  if not public.is_owner() then raise exception 'not allowed'; end if;
  return public._request_link(p_url, p_streamer, p_start, p_end, p_max, p_full_frame);
end $$;

-- `clipworker link URL` on the PC (service role only).
create or replace function public.request_link_clips_worker(p_url text, p_streamer text default null,
  p_start int default null, p_end int default null, p_max int default 6, p_full_frame boolean default false)
returns jsonb language sql security definer set search_path = public as $$
  select public._request_link(p_url, p_streamer, p_start, p_end, p_max, p_full_frame);
$$;

-- Owner cancels a request that has not finished; the PC stops at its next step.
create or replace function public.cancel_link_job(p_id uuid) returns public.link_jobs
language plpgsql security definer set search_path = public as $$
declare r public.link_jobs;
begin
  if not public.is_owner() then raise exception 'not allowed'; end if;
  update public.link_jobs set status = 'canceled', detail = 'canceled from the dashboard', finished_at = now()
   where id = p_id and status not in ('done', 'failed', 'canceled') returning * into r;
  return r;
end $$;

revoke execute on function public._request_link(text, text, int, int, int, boolean) from public, anon, authenticated;
revoke execute on function public.request_link_clips(text, text, int, int, int, boolean) from public, anon;
revoke execute on function public.request_link_clips_worker(text, text, int, int, int, boolean) from public, anon, authenticated;
revoke execute on function public.cancel_link_job(uuid) from public, anon;
grant execute on function public.request_link_clips(text, text, int, int, int, boolean) to authenticated;
grant execute on function public.cancel_link_job(uuid) to authenticated;
grant execute on function public.request_link_clips_worker(text, text, int, int, int, boolean) to service_role;

do $$ begin
  if not exists (select 1 from pg_publication_tables
                 where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'link_jobs') then
    alter publication supabase_realtime add table public.link_jobs;
  end if;
end $$;
