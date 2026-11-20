-- Clipp core schema. Worker (PC) writes with the service role; Zo's dashboard
-- reads as an authenticated owner. Every clip state change is validated and
-- audited in the database (publish-approval-gate), not only in app code.

create extension if not exists pgcrypto;

-- ---------- access ----------
create table public.owners (
  user_id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

create or replace function public.is_owner() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.owners where user_id = auth.uid());
$$;

-- ---------- reference data ----------
create table public.streamers (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  display_name text not null,
  twitch_login text,
  kick_slug text,
  created_at timestamptz not null default now()
);

create type public.campaign_status as enum ('draft', 'active', 'paused', 'ended', 'avoid');

create table public.campaign_posts (          -- raw Discord posts (own server, followed channel)
  id uuid primary key default gen_random_uuid(),
  discord_message_id text not null unique,
  discord_channel_id text not null,
  author text,
  content text not null,
  attachments jsonb not null default '[]',
  posted_at timestamptz not null,
  parsed_at timestamptz,
  parse_error text,
  created_at timestamptz not null default now()
);

create table public.campaigns (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  status public.campaign_status not null default 'draft',
  source text not null default 'manual' check (source in ('manual', 'discord')),
  source_post_id uuid references public.campaign_posts(id) on delete set null,
  source_url text,
  streamer_slugs text[] not null default '{}',     -- rights gate: only these may be captured
  platforms text[] not null default '{}',          -- e.g. {youtube,x}
  cpm_usd numeric(10,4),
  cap_usd numeric(12,2),
  deadline timestamptz,
  rules jsonb not null default '{}',               -- {min_s,max_s,required_tags[],banned_words[],notes}
  score numeric(5,2),                              -- campaign-scout score
  recommendation text,                             -- pursue / avoid + why
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index campaigns_status_idx on public.campaigns(status);

-- Publishing destinations (D005: dedicated per-streamer or shared accounts).
create table public.destinations (
  id uuid primary key default gen_random_uuid(),
  platform text not null check (platform in ('youtube', 'x')),
  label text not null,                     -- e.g. "Shorts: main". Tokens live in the worker .env, never here.
  credential_ref text not null,            -- env var prefix on the PC, e.g. YT_MAIN
  streamer_id uuid references public.streamers(id) on delete cascade,   -- null = shared
  active boolean not null default true,
  daily_cap int not null default 10 check (daily_cap > 0),
  created_at timestamptz not null default now(),
  unique (platform, label)
);

-- ---------- clips ----------
create type public.clip_state as enum
  ('qa_passed', 'pending_review', 'approved', 'revise', 'rejected', 'scheduled', 'published', 'failed');

create table public.clips (
  id uuid primary key default gen_random_uuid(),
  job_id text not null unique,                   -- worker's local job id (idempotent upload)
  streamer_id uuid references public.streamers(id),
  campaign_id uuid references public.campaigns(id),
  channel_key text not null,                     -- twitch:lacy
  state public.clip_state not null default 'pending_review',
  title text,
  hook text,
  description text,
  category text,
  confidence real,
  detector_score real,
  moment_at timestamptz not null,
  duration_s real,
  storage_path text,                             -- clips bucket
  thumb_path text,
  qa jsonb not null default '{}',
  judge jsonb not null default '{}',
  manifest jsonb not null default '{}',
  revision int not null default 0,
  reviewed_at timestamptz,
  reviewed_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index clips_state_idx on public.clips(state, created_at desc);

create table public.clip_events (              -- audit log, written by trigger only
  id bigint generated always as identity primary key,
  clip_id uuid not null references public.clips(id) on delete cascade,
  from_state public.clip_state,
  to_state public.clip_state not null,
  actor text not null check (actor in ('worker', 'human', 'system')),
  actor_id uuid,
  reason text,
  detail jsonb not null default '{}',
  at timestamptz not null default now()
);
create index clip_events_clip_idx on public.clip_events(clip_id, at);

create table public.revisions (
  id uuid primary key default gen_random_uuid(),
  clip_id uuid not null references public.clips(id) on delete cascade,
  kind text not null check (kind in ('caption', 'trim', 'crop', 'title', 'other')),
  note text not null,
  payload jsonb not null default '{}',           -- e.g. {"trim_in":1.5,"trim_out":32}
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);
create index revisions_open_idx on public.revisions(clip_id) where resolved_at is null;

create table public.publications (            -- one row per clip x destination = idempotency key
  id uuid primary key default gen_random_uuid(),
  clip_id uuid not null references public.clips(id) on delete cascade,
  destination_id uuid not null references public.destinations(id),
  status text not null default 'pending' check (status in ('pending', 'posting', 'posted', 'failed')),
  external_id text,
  url text,
  attempts int not null default 0,
  last_error text,
  response jsonb not null default '{}',
  posted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (clip_id, destination_id)
);

-- Content Rewards: Zo submits by hand within 30 min of posting (D025).
create table public.submissions (
  id uuid primary key default gen_random_uuid(),
  publication_id uuid not null unique references public.publications(id) on delete cascade,
  campaign_id uuid references public.campaigns(id),
  post_url text not null,
  posted_at timestamptz not null,
  deadline_at timestamptz not null,
  submitted_at timestamptz,
  created_at timestamptz not null default now()
);

create view public.submissions_live with (security_invoker = true) as
select s.*,
  case when s.submitted_at is not null then 'submitted'
       when now() > s.deadline_at then 'missed'
       else 'open' end as status,
  greatest(0, extract(epoch from (s.deadline_at - now())))::int as seconds_left
from public.submissions s;

-- ---------- ops ----------
create table public.worker_heartbeat (
  worker_id text primary key,
  seen_at timestamptz not null default now(),
  status jsonb not null default '{}'             -- live channels, queue depth, gpu, version, disk
);

create table public.spend (                    -- budget meter vs $100-250/mo (D012)
  id bigint generated always as identity primary key,
  kind text not null check (kind in ('grok', 'x_post', 'storage', 'transcribe', 'other')),
  amount_usd numeric(10,5) not null,
  units numeric,
  meta jsonb not null default '{}',
  at timestamptz not null default now()
);
create index spend_at_idx on public.spend(at);

create view public.spend_month with (security_invoker = true) as
select date_trunc('month', at) as month, kind, sum(amount_usd) as usd, count(*) as n
from public.spend group by 1, 2;

create table public.candidate_log (           -- detector/judge outcomes for clip-detector-tuning
  id bigint generated always as identity primary key,
  job_id text not null,
  channel_key text not null,
  moment_at timestamptz not null,
  score real not null,
  outcome text not null check (outcome in ('kept', 'dropped', 'duplicate', 'qa_failed', 'error')),
  reason text,
  features jsonb not null default '{}',
  at timestamptz not null default now()
);

-- ---------- state machine + audit ----------
create or replace function public.clip_transition_allowed(src public.clip_state, dst public.clip_state, actor text)
returns boolean language sql immutable as $$
  select case actor
    when 'worker' then (src, dst) in (
      ('qa_passed','pending_review'), ('revise','pending_review'), ('approved','scheduled'),
      ('scheduled','published'), ('scheduled','failed'), ('failed','scheduled'))
    when 'human' then (src, dst) in (
      ('pending_review','approved'), ('pending_review','revise'), ('pending_review','rejected'),
      ('approved','revise'), ('approved','rejected'), ('revise','rejected'), ('failed','rejected'))
    else false end;
$$;

create or replace function public.current_actor() returns text language sql stable as $$
  select case coalesce(auth.role(), '')
    when 'service_role' then 'worker'
    when 'authenticated' then 'human'
    else 'system' end;
$$;

create or replace function public.clips_guard() returns trigger
language plpgsql as $$
declare a text := public.current_actor();
begin
  if tg_op = 'INSERT' then
    if new.state not in ('qa_passed', 'pending_review') then
      raise exception 'clips must enter as qa_passed or pending_review, got %', new.state;
    end if;
    return new;
  end if;
  new.updated_at := now();
  if new.state is distinct from old.state then
    if not public.clip_transition_allowed(old.state, new.state, a) then
      raise exception 'clip % transition % -> % not allowed for %', old.id, old.state, new.state, a;
    end if;
    if a = 'human' then
      new.reviewed_at := now();
      new.reviewed_by := auth.uid();
    end if;
  end if;
  return new;
end $$;

create trigger clips_guard before insert or update on public.clips
for each row execute function public.clips_guard();

create or replace function public.clips_audit() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if tg_op = 'INSERT' or new.state is distinct from old.state then
    insert into public.clip_events(clip_id, from_state, to_state, actor, actor_id, reason, detail)
    values (new.id, case when tg_op = 'UPDATE' then old.state end, new.state, public.current_actor(),
            auth.uid(), nullif(current_setting('app.reason', true), ''),
            coalesce(nullif(current_setting('app.detail', true), '')::jsonb, '{}'));
  end if;
  return new;
end $$;

create trigger clips_audit after insert or update on public.clips
for each row execute function public.clips_audit();

-- A publication can only be created/posted for a clip that a human approved.
create or replace function public.publications_guard() returns trigger
language plpgsql as $$
declare s public.clip_state;
begin
  select state into s from public.clips where id = new.clip_id;
  if s not in ('approved', 'scheduled', 'published', 'failed') then
    raise exception 'publication for clip % in state % refused: needs human approval', new.clip_id, s;
  end if;
  new.updated_at := now();
  return new;
end $$;

create trigger publications_guard before insert or update on public.publications
for each row execute function public.publications_guard();

-- Posted to a campaign platform -> open the 30-minute Content Rewards countdown.
create or replace function public.publications_open_submission() returns trigger
language plpgsql security definer set search_path = public as $$
declare c uuid;
begin
  if new.status = 'posted' and new.url is not null
     and (tg_op = 'INSERT' or old.status is distinct from 'posted') then
    select campaign_id into c from public.clips where id = new.clip_id;
    insert into public.submissions(publication_id, campaign_id, post_url, posted_at, deadline_at)
    values (new.id, c, new.url, coalesce(new.posted_at, now()),
            coalesce(new.posted_at, now()) + interval '30 minutes')
    on conflict (publication_id) do nothing;
  end if;
  return new;
end $$;

create trigger publications_open_submission after insert or update on public.publications
for each row execute function public.publications_open_submission();

-- ---------- dashboard RPCs (the only write path for Zo) ----------
create or replace function public.review_clip(p_clip uuid, p_action text, p_note text default null,
                                              p_kind text default 'other', p_payload jsonb default '{}')
returns public.clips language plpgsql security definer set search_path = public as $$
declare r public.clips;
begin
  if not public.is_owner() then raise exception 'not allowed'; end if;
  if p_action not in ('approve', 'revise', 'reject') then raise exception 'bad action %', p_action; end if;
  if p_action = 'revise' and coalesce(p_note, '') = '' then raise exception 'revise needs a note'; end if;
  perform set_config('app.reason', coalesce(p_note, p_action), true);
  update public.clips set state = case p_action when 'approve' then 'approved'::public.clip_state
                                                when 'revise' then 'revise'::public.clip_state
                                                else 'rejected'::public.clip_state end
  where id = p_clip returning * into r;
  if r.id is null then raise exception 'clip % not found', p_clip; end if;
  if p_action = 'revise' then
    insert into public.revisions(clip_id, kind, note, payload, created_by)
    values (p_clip, p_kind, p_note, p_payload, auth.uid());
  end if;
  return r;
end $$;

create or replace function public.mark_submitted(p_submission uuid)
returns public.submissions language plpgsql security definer set search_path = public as $$
declare r public.submissions;
begin
  if not public.is_owner() then raise exception 'not allowed'; end if;
  update public.submissions set submitted_at = coalesce(submitted_at, now())
  where id = p_submission returning * into r;
  return r;
end $$;

-- ---------- RLS: owners read everything; writes go through RPCs ----------
do $$
declare t text;
begin
  foreach t in array array['owners','streamers','campaign_posts','campaigns','destinations','clips',
                           'clip_events','revisions','publications','submissions','worker_heartbeat',
                           'spend','candidate_log']
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('create policy owner_read on public.%I for select to authenticated using (public.is_owner())', t);
  end loop;
end $$;

create policy owner_write_campaigns on public.campaigns for update to authenticated
  using (public.is_owner()) with check (public.is_owner());
create policy owner_insert_campaigns on public.campaigns for insert to authenticated
  with check (public.is_owner());

revoke execute on function public.review_clip(uuid, text, text, text, jsonb) from public, anon;
revoke execute on function public.mark_submitted(uuid) from public, anon;
grant execute on function public.review_clip(uuid, text, text, text, jsonb) to authenticated;
grant execute on function public.mark_submitted(uuid) to authenticated;

-- ---------- storage: private bucket, signed URLs for phone download (D021) ----------
insert into storage.buckets (id, name, public, file_size_limit)
values ('clips', 'clips', false, 52428800)
on conflict (id) do nothing;

create policy owner_read_clips on storage.objects for select to authenticated
  using (bucket_id = 'clips' and public.is_owner());

-- ---------- realtime for the dashboard ----------
alter publication supabase_realtime add table public.clips, public.worker_heartbeat, public.submissions;

-- Worker write path with an audit reason (service role only).
create or replace function public.worker_transition(p_clip uuid, p_to public.clip_state,
                                                    p_reason text default null, p_detail jsonb default '{}')
returns public.clips language plpgsql security invoker set search_path = public as $$
declare r public.clips;
begin
  perform set_config('app.reason', coalesce(p_reason, ''), true);
  perform set_config('app.detail', coalesce(p_detail, '{}')::text, true);
  update public.clips set state = p_to where id = p_clip returning * into r;
  if r.id is null then raise exception 'clip % not found', p_clip; end if;
  return r;
end $$;
revoke execute on function public.worker_transition(uuid, public.clip_state, text, jsonb) from public, anon, authenticated;
grant execute on function public.worker_transition(uuid, public.clip_state, text, jsonb) to service_role;
