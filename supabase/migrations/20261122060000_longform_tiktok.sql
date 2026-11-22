-- Long-form TikTok videos for Zwoclipp (D079-D082). Videos enter the normal review queue as
-- clips (category 'longform'); this table carries their test tags, the manual TikTok post,
-- and the stats zo enters from TikTok Studio so the test cells can be ranked.

alter table public.destinations drop constraint if exists destinations_platform_check;
alter table public.destinations add constraint destinations_platform_check
  check (platform in ('youtube', 'x', 'tiktok'));

create table public.longform_videos (
  id text primary key,                                   -- worker plan id
  clip_id uuid unique references public.clips(id) on delete cascade,
  channel text not null default 'zwoclipp',
  format text not null check (format in ('recap', 'topn', 'explainer', 'extended')),
  pacing text not null check (pacing in ('short', 'long')),
  caption_style text not null check (caption_style in ('A', 'B')),   -- D073
  voice text not null check (voice in ('ai', 'zo')),
  layout text not null check (layout in ('switch', 'stacked')),
  beat_job_ids text[] not null default '{}',
  runtime_s real not null check (runtime_s > 60),        -- Creator Rewards pays on over 1 minute
  coverage real,                                         -- narration share of runtime
  script jsonb not null default '{}',
  tiktok_url text,
  posted_at timestamptz,
  notice text not null default 'none' check (notice in ('none', 'ineligible', 'unoriginal')),
  created_at timestamptz not null default now()
);

create table public.tiktok_stats (
  id uuid primary key default gen_random_uuid(),
  video_id text not null references public.longform_videos(id) on delete cascade,
  views int check (views >= 0),
  for_you_views int check (for_you_views >= 0),
  qualified_views int check (qualified_views >= 0),
  avg_watch_s real check (avg_watch_s >= 0),
  watched_full_pct real check (watched_full_pct between 0 and 100),
  hold_5s_pct real check (hold_5s_pct between 0 and 100),
  follows int check (follows >= 0),
  search_views_pct real check (search_views_pct between 0 and 100),
  rewards_usd numeric(10,2) check (rewards_usd >= 0),
  entered_at timestamptz not null default now()
);
create index tiktok_stats_video_idx on public.tiktok_stats(video_id, entered_at desc);

alter table public.longform_videos enable row level security;
alter table public.tiktok_stats enable row level security;
create policy owner_read on public.longform_videos for select to authenticated using (public.is_owner());
create policy owner_read on public.tiktok_stats for select to authenticated using (public.is_owner());
create policy owner_insert_stats on public.tiktok_stats for insert to authenticated
  with check (public.is_owner());

-- zo marks a video posted (manual upload until TikTok's app audit, D074). Only approved videos.
create or replace function public.mark_tiktok_posted(p_video text, p_url text)
returns public.longform_videos language plpgsql security definer set search_path = public as $$
declare r public.longform_videos; st public.clip_state;
begin
  if not public.is_owner() then raise exception 'not allowed'; end if;
  if coalesce(p_url, '') !~ '^https://(www\.|vm\.)?tiktok\.com/' then raise exception 'not a TikTok link'; end if;
  select c.state into st from public.longform_videos v join public.clips c on c.id = v.clip_id where v.id = p_video;
  if st is null then raise exception 'video % not found', p_video; end if;
  if st <> 'approved' then raise exception 'video must be approved before posting (state %)', st; end if;
  update public.longform_videos set tiktok_url = p_url, posted_at = coalesce(posted_at, now())
  where id = p_video returning * into r;
  return r;
end $$;

-- D082 kill rule input: zo records a TikTok eligibility notice on a video.
create or replace function public.set_tiktok_notice(p_video text, p_notice text)
returns public.longform_videos language plpgsql security definer set search_path = public as $$
declare r public.longform_videos;
begin
  if not public.is_owner() then raise exception 'not allowed'; end if;
  update public.longform_videos set notice = p_notice where id = p_video returning * into r;
  if r.id is null then raise exception 'video % not found', p_video; end if;
  return r;
end $$;

revoke execute on function public.mark_tiktok_posted(text, text) from public, anon;
revoke execute on function public.set_tiktok_notice(text, text) from public, anon;
grant execute on function public.mark_tiktok_posted(text, text) to authenticated;
grant execute on function public.set_tiktok_notice(text, text) to authenticated;

-- Per-cell results: latest stats per posted video, rolled up by test tags.
create or replace view public.longform_results with (security_invoker = true) as
with latest as (
  select distinct on (video_id) * from public.tiktok_stats order by video_id, entered_at desc
)
select v.format, v.pacing, v.caption_style, v.voice, v.layout,
       count(*) filter (where v.posted_at is not null) as posts,
       count(*) filter (where v.notice <> 'none') as notices,
       round(avg(l.avg_watch_s)::numeric, 1) as avg_watch_s,
       round(avg(l.hold_5s_pct)::numeric, 1) as hold_5s_pct,
       round((sum(l.follows)::numeric * 1000 / nullif(sum(l.views), 0)), 2) as follows_per_1k,
       round((sum(l.rewards_usd) * 1000 / nullif(sum(l.qualified_views), 0)), 2) as rpm_usd
from public.longform_videos v left join latest l on l.video_id = v.id
group by 1, 2, 3, 4, 5;
