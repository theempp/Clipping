-- Broadcast dashboard (D099): live numbers, growth history, streamer brain weights.
-- NOT applied to the live project yet: Zo applies it after review.
--
-- live_stats      one row per channel (streamers on Twitch/Kick, Zo's own YouTube/X/TikTok). Written only by the
--                 server route /api/live with the service role; the dashboard reads it and gets Realtime pushes.
-- stat_snapshots  thinned history for the growth charts (own channels ~hourly, live viewers ~every 10 min).
-- streamer_brain  per-streamer detector weights + chat words (Streamer Brain, D089); Zo can tune them.

create table if not exists public.live_stats (
  key text primary key,                                   -- twitch:lacy, kick:adinross, youtube:own, x:own, tiktok:own
  kind text not null check (kind in ('streamer', 'own')),
  platform text not null check (platform in ('twitch', 'kick', 'youtube', 'x', 'tiktok')),
  is_live boolean,
  viewers int,
  followers bigint,
  views bigint,
  posts int,
  title text,
  game text,
  started_at timestamptz,
  avatar_url text,
  updated_at timestamptz not null default now()
);

create table if not exists public.stat_snapshots (
  id bigint generated always as identity primary key,
  key text not null,
  metric text not null check (metric in ('followers', 'views', 'posts', 'viewers')),
  value numeric not null,
  at timestamptz not null default now(),
  slot bigint                                             -- time bucket from /api/live; null for manual entries
);
create index if not exists stat_snapshots_key_at on public.stat_snapshots(key, at desc);
-- Two dashboards (or the cron and a dashboard) polling at once write one point per bucket, not two.
create unique index if not exists stat_snapshots_slot on public.stat_snapshots(key, metric, slot);

create table if not exists public.streamer_brain (
  streamer_id uuid primary key references public.streamers(id) on delete cascade,
  weights jsonb not null default '{"chat_spike":70,"voice_peak":55,"chat_words":75,"viewer_clips":35,"approved_match":60}',
  words text[] not null default '{}',
  updated_at timestamptz not null default now(),
  updated_by uuid references auth.users(id)
);

alter table public.live_stats enable row level security;
alter table public.stat_snapshots enable row level security;
alter table public.streamer_brain enable row level security;
-- Safe to re-run: policies are dropped first. No insert/update/delete policies: writes go through the
-- service role (/api/live) or the security-definer RPCs below.
drop policy if exists owner_read on public.live_stats;
drop policy if exists owner_read on public.stat_snapshots;
drop policy if exists owner_read on public.streamer_brain;
create policy owner_read on public.live_stats for select to authenticated using (public.is_owner());
create policy owner_read on public.stat_snapshots for select to authenticated using (public.is_owner());
create policy owner_read on public.streamer_brain for select to authenticated using (public.is_owner());

-- Owner edits brain weights from Settings. Numbers are rounded and clamped 0-100; unknown keys, nulls and
-- non-numbers are dropped (least() ignores NULL, so a null must never reach it). A first save starts from the
-- column defaults, so saving one slider never blanks the others. Words: trimmed, lower-case, max 50 x 40 chars.
create or replace function public.set_brain_weights(p_streamer uuid, p_weights jsonb, p_words text[] default null)
returns public.streamer_brain language plpgsql security definer set search_path = public as $$
declare r public.streamer_brain; w jsonb := '{}'; k text; v text; ws text[];
  base constant jsonb := '{"chat_spike":70,"voice_peak":55,"chat_words":75,"viewer_clips":35,"approved_match":60}';
begin
  if not public.is_owner() then raise exception 'not allowed'; end if;
  if jsonb_typeof(coalesce(p_weights, '{}')) <> 'object' then raise exception 'weights must be an object'; end if;
  foreach k in array array['chat_spike','voice_peak','chat_words','viewer_clips','approved_match'] loop
    v := p_weights->>k;
    if v ~ '^\s*-?[0-9]+(\.[0-9]+)?\s*$' then
      w := w || jsonb_build_object(k, greatest(0, least(100, round(v::numeric)))::int);
    end if;
  end loop;
  if p_words is not null then
    select coalesce(array_agg(distinct x), '{}') into ws from (
      select left(lower(btrim(u)), 40) x from unnest(p_words) u where btrim(coalesce(u, '')) <> '' limit 50) t;
  end if;
  insert into public.streamer_brain(streamer_id, weights, words, updated_at, updated_by)
  values (p_streamer, base || w, coalesce(ws, '{}'), now(), auth.uid())
  on conflict (streamer_id) do update
    set weights = streamer_brain.weights || w,
        words = coalesce(ws, streamer_brain.words), updated_at = now(), updated_by = auth.uid()
  returning * into r;
  return r;
end $$;

-- TikTok has no API until the audit (D074): Zo types the channel numbers in.
create or replace function public.set_manual_stat(p_followers bigint, p_views bigint, p_posts int)
returns public.live_stats language plpgsql security definer set search_path = public as $$
declare r public.live_stats;
begin
  if not public.is_owner() then raise exception 'not allowed'; end if;
  if least(p_followers, p_views, p_posts) < 0 then raise exception 'counts cannot be negative'; end if;
  -- A blank (null) field keeps the last typed number instead of wiping it.
  insert into public.live_stats(key, kind, platform, followers, views, posts, updated_at)
  values ('tiktok:own', 'own', 'tiktok', p_followers, p_views, p_posts, now())
  on conflict (key) do update set followers = coalesce(excluded.followers, live_stats.followers),
    views = coalesce(excluded.views, live_stats.views), posts = coalesce(excluded.posts, live_stats.posts),
    updated_at = now()
  returning * into r;
  insert into public.stat_snapshots(key, metric, value)
  select 'tiktok:own', m, v from (values ('followers', p_followers::numeric), ('views', p_views::numeric), ('posts', p_posts::numeric)) x(m, v)
  where v is not null;
  return r;
end $$;

revoke execute on function public.set_brain_weights(uuid, jsonb, text[]) from public, anon;
revoke execute on function public.set_manual_stat(bigint, bigint, int) from public, anon;
grant execute on function public.set_brain_weights(uuid, jsonb, text[]) to authenticated;
grant execute on function public.set_manual_stat(bigint, bigint, int) to authenticated;

-- Realtime pushes; skip tables already in the publication so a re-run does not fail.
do $$ declare t text; begin
  foreach t in array array['live_stats', 'streamer_brain'] loop
    if not exists (select 1 from pg_publication_tables
                   where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = t) then
      execute format('alter publication supabase_realtime add table public.%I', t);
    end if;
  end loop;
end $$;

-- Schedule: supabase/snippets/schedule_live_stats.sql (pg_cron + pg_net + Vault secret), run after deploy.
