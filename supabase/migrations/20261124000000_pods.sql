-- Pods + ledger (D091-D097). NOT applied to the live project: Zo applies it after review.
--
-- Access model
--   agency admin = a row in public.owners (unchanged, D054/D061). is_admin() wraps is_owner(), so every existing
--                  owner_read policy and owner RPC keeps working and the admin sees every pod.
--   pod member   = a row in public.pod_members (role owner | member). Reads only rows of pods they belong to.
--                  Reviews only their own pod's clips. Read-only on the ledger.
--   worker       = service_role (bypasses RLS). Tags every clip / candidate with a pod (one shared GPU queue, D096).
-- Money: the dashboard never moves money (D092). The ledger only records; Zo approves, sends, marks paid.
-- Safe to re-run: if-not-exists everywhere, policies dropped before create, backfills only touch nulls.

-- ---------- pods ----------
create table if not exists public.pods (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  status text not null default 'active' check (status in ('trial', 'active', 'ended')),
  trial_ends_at date,                                     -- D093: 90-day trial
  ended_at timestamptz,                                   -- D093: tool access ends; members are removed
  created_at timestamptz not null default now()
);
insert into public.pods(slug, name, status) values ('pod-1', 'Pod 1', 'active') on conflict (slug) do nothing;

create table if not exists public.pod_members (
  pod_id uuid not null references public.pods(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'member' check (role in ('owner', 'member')),
  added_at timestamptz not null default now(),
  primary key (pod_id, user_id)
);
create index if not exists pod_members_user_idx on public.pod_members(user_id);

-- ---------- helpers (security definer, fixed search_path) ----------
create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select public.is_owner();
$$;

create or replace function public.my_pod_ids() returns setof uuid
language sql stable security definer set search_path = public as $$
  select pod_id from public.pod_members where user_id = auth.uid();
$$;

create or replace function public.default_pod_id() returns uuid
language sql stable security definer set search_path = public as $$
  select id from public.pods where slug = 'pod-1';
$$;

-- Replaces the dashboard's is_owner() gate: who am I, which pods can I see.
create or replace function public.my_access() returns jsonb
language sql stable security definer set search_path = public as $$
  select jsonb_build_object(
    'admin', public.is_admin(),
    'pods', coalesce((select jsonb_agg(jsonb_build_object('id', p.id, 'slug', p.slug, 'name', p.name, 'role', m.role)
                                       order by p.slug)
                      from public.pod_members m join public.pods p on p.id = m.pod_id
                      where m.user_id = auth.uid()), '[]'::jsonb));
$$;

-- Existing owner(s) become Pod 1 owners.
insert into public.pod_members(pod_id, user_id, role)
select public.default_pod_id(), user_id, 'owner' from public.owners
on conflict do nothing;

-- ---------- pod tag on existing tables (Pod 1 backfill) ----------
alter table public.streamers add column if not exists pod_id uuid references public.pods(id);
update public.streamers set pod_id = public.default_pod_id() where pod_id is null;
alter table public.streamers alter column pod_id set default public.default_pod_id();
alter table public.streamers alter column pod_id set not null;
create index if not exists streamers_pod_idx on public.streamers(pod_id);

alter table public.destinations add column if not exists pod_id uuid references public.pods(id);
update public.destinations set pod_id = public.default_pod_id() where pod_id is null;
alter table public.destinations alter column pod_id set default public.default_pod_id();
alter table public.destinations alter column pod_id set not null;

-- clips: nullable until the worker sends pod_id itself (build-plan Phase 1). Null = admin-only.
alter table public.clips add column if not exists pod_id uuid references public.pods(id);
update public.clips set pod_id = public.default_pod_id() where pod_id is null;
create index if not exists clips_pod_state_idx on public.clips(pod_id, state, created_at desc);

-- No jobs table exists (the worker queue is local). The pod tag on a job lands on its clip and candidate rows.
alter table public.candidate_log add column if not exists pod_id uuid references public.pods(id);
update public.candidate_log set pod_id = public.default_pod_id() where pod_id is null;

-- Worker inserts without pod_id get it from the streamer (by id, then by channel_key login).
create or replace function public.clips_pod_tag() returns trigger
language plpgsql set search_path = public as $$
declare plat text := split_part(new.channel_key, ':', 1); login text := lower(split_part(new.channel_key, ':', 2));
begin
  if new.pod_id is null and new.streamer_id is not null then
    select pod_id into new.pod_id from public.streamers where id = new.streamer_id;
  end if;
  if new.pod_id is null then
    select pod_id into new.pod_id from public.streamers
    where (plat = 'twitch' and lower(twitch_login) = login) or (plat = 'kick' and lower(kick_slug) = login)
    limit 1;
  end if;
  return new;
end $$;
drop trigger if exists clips_pod_tag on public.clips;
create trigger clips_pod_tag before insert on public.clips for each row execute function public.clips_pod_tag();

-- Campaign participation per pod. Campaigns stay one shared list; the per-pod scout writes suggestions here.
create table if not exists public.pod_campaigns (
  pod_id uuid not null references public.pods(id) on delete cascade,
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  status text not null default 'suggested' check (status in ('suggested', 'joined', 'declined', 'left')),
  scout jsonb not null default '{}',                      -- per-pod scout score, flags, reasons
  decided_by uuid references auth.users(id),
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  primary key (pod_id, campaign_id)
);
insert into public.pod_campaigns(pod_id, campaign_id, status)
select public.default_pod_id(), id, 'joined' from public.campaigns where status = 'active'
on conflict do nothing;

-- ---------- review RPCs: admin or a member of the clip's pod ----------
create or replace function public.review_clip(p_clip uuid, p_action text, p_note text default null,
                                              p_kind text default 'other', p_payload jsonb default '{}')
returns public.clips language plpgsql security definer set search_path = public as $$
declare r public.clips;
begin
  if not (public.is_admin() or exists (select 1 from public.clips
          where id = p_clip and pod_id in (select public.my_pod_ids()))) then
    raise exception 'not allowed';
  end if;
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
  if not (public.is_admin() or exists (
      select 1 from public.submissions s join public.publications p on p.id = s.publication_id
      join public.clips c on c.id = p.clip_id
      where s.id = p_submission and c.pod_id in (select public.my_pod_ids()))) then
    raise exception 'not allowed';
  end if;
  update public.submissions set submitted_at = coalesce(submitted_at, now())
  where id = p_submission returning * into r;
  return r;
end $$;

-- ---------- ledger ----------
do $$ begin
  if not exists (select 1 from pg_type where typname = 'ledger_status' and typnamespace = 'public'::regnamespace) then
    create type public.ledger_status as enum ('pending', 'cleared', 'approved', 'paid');
  end if;
end $$;

create table if not exists public.ledger_entries (
  id uuid primary key default gen_random_uuid(),
  pod_id uuid not null references public.pods(id),
  source text not null default 'campaign' check (source in ('campaign')),   -- v1: campaign payouts only (D092)
  source_ref text not null,                               -- payout id / reference from Content Rewards, Whop, ...
  campaign_id uuid references public.campaigns(id),
  gross_cents bigint not null check (gross_cents >= 0),
  agency_rate numeric(5,4) not null default 0.15 check (agency_rate between 0 and 1),   -- D091, recorded per row
  agency_cut_cents bigint generated always as (round(gross_cents * agency_rate)::bigint) stored,
  pod_net_cents bigint generated always as (gross_cents - round(gross_cents * agency_rate)::bigint) stored,
  status public.ledger_status not null default 'pending',
  note text,
  cleared_at timestamptz,                                 -- money landed in the agency account (D092)
  approved_by uuid references auth.users(id),
  approved_at timestamptz,
  paid_by uuid references auth.users(id),
  paid_at timestamptz,
  paid_ref text,                                          -- Zo's transfer reference; required for paid
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (pod_id, source, source_ref)
);
create index if not exists ledger_entries_pod_idx on public.ledger_entries(pod_id, status, created_at desc);

create table if not exists public.ledger_events (       -- append-only audit, trigger-written
  id bigint generated always as identity primary key,
  entry_id uuid not null references public.ledger_entries(id) on delete restrict,
  pod_id uuid not null,
  op text not null check (op in ('insert', 'update')),
  from_status public.ledger_status,
  to_status public.ledger_status not null,
  actor text not null,
  actor_id uuid,
  row_after jsonb not null,
  at timestamptz not null default now()
);
create index if not exists ledger_events_entry_idx on public.ledger_events(entry_id, at);

-- Only pending -> cleared -> approved -> paid, only by the admin; amounts lock once cleared; paid is final.
create or replace function public.ledger_guard() returns trigger
language plpgsql set search_path = public as $$
begin
  if tg_op = 'DELETE' then raise exception 'ledger entries are permanent'; end if;
  if tg_op = 'INSERT' then
    if not (public.is_admin() or public.current_actor() = 'worker') then raise exception 'not allowed'; end if;
    if new.status <> 'pending' then raise exception 'ledger entries start pending'; end if;
    new.cleared_at := null; new.approved_by := null; new.approved_at := null;
    new.paid_by := null; new.paid_at := null; new.paid_ref := null;
    new.created_by := auth.uid();
    return new;
  end if;
  if not public.is_admin() then raise exception 'only the agency admin changes ledger entries'; end if;
  if old.status = 'paid' then raise exception 'ledger entry % is paid and final', old.id; end if;
  if (new.pod_id, new.source, new.source_ref, new.campaign_id, new.gross_cents, new.agency_rate)
     is distinct from (old.pod_id, old.source, old.source_ref, old.campaign_id, old.gross_cents, old.agency_rate)
     and old.status <> 'pending' then
    raise exception 'ledger entry % amounts are locked after pending', old.id;
  end if;
  -- stamps are set here, never by the caller
  new.cleared_at := old.cleared_at; new.approved_by := old.approved_by; new.approved_at := old.approved_at;
  new.paid_by := old.paid_by; new.paid_at := old.paid_at; new.created_by := old.created_by;
  new.created_at := old.created_at; new.updated_at := now();
  if new.status is distinct from old.status then
    if (old.status, new.status) = ('pending', 'cleared') then
      new.cleared_at := now();
    elsif (old.status, new.status) = ('cleared', 'approved') then
      new.approved_by := auth.uid(); new.approved_at := now();
    elsif (old.status, new.status) = ('approved', 'paid') then
      if nullif(btrim(coalesce(new.paid_ref, '')), '') is null then raise exception 'paid needs a transfer reference'; end if;
      new.paid_by := auth.uid(); new.paid_at := now();
    else
      raise exception 'ledger transition % -> % not allowed', old.status, new.status;
    end if;
  end if;
  if new.status <> 'paid' then new.paid_ref := old.paid_ref; end if;
  return new;
end $$;
drop trigger if exists ledger_guard on public.ledger_entries;
create trigger ledger_guard before insert or update or delete on public.ledger_entries
for each row execute function public.ledger_guard();

create or replace function public.ledger_audit() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.ledger_events(entry_id, pod_id, op, from_status, to_status, actor, actor_id, row_after)
  values (new.id, new.pod_id, lower(tg_op), case when tg_op = 'UPDATE' then old.status end, new.status,
          public.current_actor(), auth.uid(), to_jsonb(new));
  return new;
end $$;
drop trigger if exists ledger_audit on public.ledger_entries;
create trigger ledger_audit after insert or update on public.ledger_entries
for each row execute function public.ledger_audit();

create or replace function public.no_rewrite() returns trigger
language plpgsql set search_path = public as $$
begin
  raise exception '% is append-only (% refused)', tg_table_name, tg_op;
end $$;
drop trigger if exists ledger_events_append_only on public.ledger_events;
create trigger ledger_events_append_only before update or delete on public.ledger_events
for each row execute function public.no_rewrite();
drop trigger if exists ledger_events_no_truncate on public.ledger_events;
create trigger ledger_events_no_truncate before truncate on public.ledger_events
for each statement execute function public.no_rewrite();
drop trigger if exists ledger_entries_no_truncate on public.ledger_entries;
create trigger ledger_entries_no_truncate before truncate on public.ledger_entries
for each statement execute function public.no_rewrite();

-- Admin write path (record only; nothing here moves money).
create or replace function public.ledger_add(p_pod uuid, p_campaign uuid, p_source_ref text, p_gross_cents bigint,
                                             p_note text default null, p_rate numeric default 0.15)
returns public.ledger_entries language plpgsql security definer set search_path = public as $$
declare r public.ledger_entries;
begin
  if not public.is_admin() then raise exception 'not allowed'; end if;
  insert into public.ledger_entries(pod_id, campaign_id, source_ref, gross_cents, agency_rate, note)
  values (p_pod, p_campaign, p_source_ref, p_gross_cents, coalesce(p_rate, 0.15), p_note)
  returning * into r;
  return r;
end $$;

create or replace function public.ledger_set_status(p_entry uuid, p_status public.ledger_status, p_ref text default null)
returns public.ledger_entries language plpgsql security definer set search_path = public as $$
declare r public.ledger_entries;
begin
  if not public.is_admin() then raise exception 'not allowed'; end if;
  update public.ledger_entries set status = p_status, paid_ref = case when p_status = 'paid' then p_ref else paid_ref end
  where id = p_entry returning * into r;
  if r.id is null then raise exception 'ledger entry % not found', p_entry; end if;
  return r;
end $$;

-- Read-only statement per pod per month (itemized rows = ledger_entries itself).
create or replace view public.pod_statements with (security_invoker = true) as
select pod_id,
       date_trunc('month', coalesce(cleared_at, created_at))::date as month,
       count(*) as entries,
       sum(gross_cents) as gross_cents,
       sum(agency_cut_cents) as agency_cut_cents,
       sum(pod_net_cents) as pod_net_cents,
       coalesce(sum(pod_net_cents) filter (where status = 'pending'), 0) as pending_net_cents,
       coalesce(sum(pod_net_cents) filter (where status in ('cleared', 'approved')), 0) as owed_net_cents,
       coalesce(sum(pod_net_cents) filter (where status = 'paid'), 0) as paid_net_cents
from public.ledger_entries
group by 1, 2;

-- ---------- RLS ----------
alter table public.pods enable row level security;
alter table public.pod_members enable row level security;
alter table public.pod_campaigns enable row level security;
alter table public.ledger_entries enable row level security;
alter table public.ledger_events enable row level security;

do $$
declare t text;
begin
  -- admin reads everything on the new tables (same owner_read pattern as core)
  foreach t in array array['pods', 'pod_members', 'pod_campaigns', 'ledger_entries', 'ledger_events'] loop
    execute format('drop policy if exists owner_read on public.%I', t);
    execute format('create policy owner_read on public.%I for select to authenticated using (public.is_admin())', t);
  end loop;
  -- members read their own pod's rows (tables with pod_id)
  foreach t in array array['pod_members', 'pod_campaigns', 'streamers', 'destinations', 'clips',
                           'candidate_log', 'ledger_entries', 'ledger_events'] loop
    execute format('drop policy if exists pod_read on public.%I', t);
    execute format('create policy pod_read on public.%I for select to authenticated using (pod_id in (select public.my_pod_ids()))', t);
  end loop;
end $$;

drop policy if exists pod_read on public.pods;
create policy pod_read on public.pods for select to authenticated using (id in (select public.my_pod_ids()));

drop policy if exists pod_read on public.campaigns;
create policy pod_read on public.campaigns for select to authenticated using (exists (
  select 1 from public.pod_campaigns pc where pc.campaign_id = campaigns.id and pc.pod_id in (select public.my_pod_ids())));

drop policy if exists pod_read on public.clip_events;
create policy pod_read on public.clip_events for select to authenticated using (exists (
  select 1 from public.clips c where c.id = clip_events.clip_id and c.pod_id in (select public.my_pod_ids())));
drop policy if exists pod_read on public.revisions;
create policy pod_read on public.revisions for select to authenticated using (exists (
  select 1 from public.clips c where c.id = revisions.clip_id and c.pod_id in (select public.my_pod_ids())));
drop policy if exists pod_read on public.publications;
create policy pod_read on public.publications for select to authenticated using (exists (
  select 1 from public.clips c where c.id = publications.clip_id and c.pod_id in (select public.my_pod_ids())));
drop policy if exists pod_read on public.submissions;
create policy pod_read on public.submissions for select to authenticated using (exists (
  select 1 from public.publications p join public.clips c on c.id = p.clip_id
  where p.id = submissions.publication_id and c.pod_id in (select public.my_pod_ids())));
drop policy if exists pod_read on public.streamer_brain;
create policy pod_read on public.streamer_brain for select to authenticated using (exists (
  select 1 from public.streamers s where s.id = streamer_brain.streamer_id and s.pod_id in (select public.my_pod_ids())));

drop policy if exists pod_read_clips on storage.objects;
create policy pod_read_clips on storage.objects for select to authenticated using (
  bucket_id = 'clips' and exists (select 1 from public.clips c
    where c.pod_id in (select public.my_pod_ids()) and storage.objects.name in (c.storage_path, c.thumb_path, c.source_path)));

-- No insert/update/delete policies on pod or ledger tables: writes go through the RPCs above or the service role.

-- ---------- grants ----------
revoke execute on function public.clips_pod_tag() from public, anon, authenticated;
revoke execute on function public.ledger_guard() from public, anon, authenticated;
revoke execute on function public.ledger_audit() from public, anon, authenticated;
revoke execute on function public.no_rewrite() from public, anon, authenticated;
revoke update, delete, truncate on public.ledger_events from anon, authenticated;
revoke delete, truncate on public.ledger_entries from anon, authenticated;
revoke execute on function public.is_admin() from public, anon;
revoke execute on function public.my_pod_ids() from public, anon;
revoke execute on function public.default_pod_id() from public, anon;
revoke execute on function public.my_access() from public, anon;
revoke execute on function public.ledger_add(uuid, uuid, text, bigint, text, numeric) from public, anon;
revoke execute on function public.ledger_set_status(uuid, public.ledger_status, text) from public, anon;
grant execute on function public.is_admin() to authenticated;
grant execute on function public.my_pod_ids() to authenticated;
grant execute on function public.default_pod_id() to authenticated, service_role;
grant execute on function public.my_access() to authenticated;
grant execute on function public.ledger_add(uuid, uuid, text, bigint, text, numeric) to authenticated;
grant execute on function public.ledger_set_status(uuid, public.ledger_status, text) to authenticated;

-- ================= Amendments from Zo's answers (D102-D108) =================
-- D102 admin sees every pod but approves only untagged clips; D103 only the pod owner approves;
-- D105 corrections are reversing entries; D106 pod owner joins campaigns; D107 an ended pod keeps
-- read-only ledger access until fully paid; D108 pod owner tunes its own streamers' brain.

create or replace function public.is_pod_owner(p_pod uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.pod_members m join public.pods p on p.id = m.pod_id
                 where m.pod_id = p_pod and m.user_id = auth.uid() and m.role = 'owner' and p.status <> 'ended');
$$;

-- Tool access ends on exit (D093): ended pods drop out of my_pod_ids().
create or replace function public.my_pod_ids() returns setof uuid
language sql stable security definer set search_path = public as $$
  select m.pod_id from public.pod_members m join public.pods p on p.id = m.pod_id
  where m.user_id = auth.uid() and p.status <> 'ended';
$$;

-- Ledger reads also cover an ended pod while any entry is unpaid (D107).
create or replace function public.my_ledger_pod_ids() returns setof uuid
language sql stable security definer set search_path = public as $$
  select m.pod_id from public.pod_members m join public.pods p on p.id = m.pod_id
  where m.user_id = auth.uid()
    and (p.status <> 'ended' or exists (select 1 from public.ledger_entries e
                                        where e.pod_id = p.id and e.status <> 'paid'));
$$;

drop policy if exists pod_read on public.ledger_entries;
create policy pod_read on public.ledger_entries for select to authenticated
  using (pod_id in (select public.my_ledger_pod_ids()));
drop policy if exists pod_read on public.ledger_events;
create policy pod_read on public.ledger_events for select to authenticated
  using (pod_id in (select public.my_ledger_pod_ids()));
drop policy if exists pod_read_ledger on public.pods;
create policy pod_read_ledger on public.pods for select to authenticated
  using (id in (select public.my_ledger_pod_ids()));

-- Review: only the owner of the clip's pod (D102, D103). Untagged clips stay admin-only.
create or replace function public.review_clip(p_clip uuid, p_action text, p_note text default null,
                                              p_kind text default 'other', p_payload jsonb default '{}')
returns public.clips language plpgsql security definer set search_path = public as $$
declare r public.clips; v_pod uuid;
begin
  select pod_id into v_pod from public.clips where id = p_clip;
  if not ((v_pod is not null and public.is_pod_owner(v_pod)) or (v_pod is null and public.is_admin())) then
    raise exception 'not allowed';
  end if;
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
declare r public.submissions; v_pod uuid; v_found boolean;
begin
  select c.pod_id, true into v_pod, v_found from public.submissions s
    join public.publications p on p.id = s.publication_id join public.clips c on c.id = p.clip_id
    where s.id = p_submission;
  if not coalesce(v_found, false) then raise exception 'submission % not found', p_submission; end if;
  if not ((v_pod is not null and public.is_pod_owner(v_pod)) or (v_pod is null and public.is_admin())) then
    raise exception 'not allowed';
  end if;
  update public.submissions set submitted_at = coalesce(submitted_at, now())
  where id = p_submission returning * into r;
  return r;
end $$;

-- Corrections = reversing entries (D105): negative gross, linked to the original, same status flow.
alter table public.ledger_entries add column if not exists reverses_id uuid references public.ledger_entries(id);
alter table public.ledger_entries drop constraint if exists ledger_entries_gross_cents_check;
alter table public.ledger_entries drop constraint if exists ledger_entries_source_check;
alter table public.ledger_entries drop constraint if exists ledger_entries_sign_check;
alter table public.ledger_entries add constraint ledger_entries_source_check check (source in ('campaign', 'reversal'));
alter table public.ledger_entries add constraint ledger_entries_sign_check check (
  (source = 'campaign' and reverses_id is null and gross_cents >= 0) or
  (source = 'reversal' and reverses_id is not null and gross_cents < 0));
create unique index if not exists ledger_entries_one_reversal on public.ledger_entries(reverses_id)
  where reverses_id is not null;

create or replace function public.ledger_reverse(p_entry uuid, p_note text)
returns public.ledger_entries language plpgsql security definer set search_path = public as $$
declare o public.ledger_entries; r public.ledger_entries;
begin
  if not public.is_admin() then raise exception 'not allowed'; end if;
  if coalesce(p_note, '') = '' then raise exception 'a reversal needs a reason'; end if;
  select * into o from public.ledger_entries where id = p_entry;
  if o.id is null then raise exception 'ledger entry % not found', p_entry; end if;
  if o.source = 'reversal' then raise exception 'cannot reverse a reversal'; end if;
  insert into public.ledger_entries(pod_id, source, source_ref, campaign_id, gross_cents, agency_rate, note, reverses_id)
  values (o.pod_id, 'reversal', 'rev:' || o.id, o.campaign_id, -o.gross_cents, o.agency_rate, p_note, o.id)
  returning * into r;
  return r;
end $$;

-- Pod owner joins / declines / leaves campaigns for its pod (D106).
create or replace function public.pod_campaign_set(p_pod uuid, p_campaign uuid, p_status text)
returns public.pod_campaigns language plpgsql security definer set search_path = public as $$
declare r public.pod_campaigns;
begin
  if not public.is_pod_owner(p_pod) then raise exception 'not allowed'; end if;
  if p_status not in ('joined', 'declined', 'left') then raise exception 'bad status %', p_status; end if;
  insert into public.pod_campaigns(pod_id, campaign_id, status) values (p_pod, p_campaign, p_status)
  on conflict (pod_id, campaign_id) do update set status = excluded.status
  returning * into r;
  return r;
end $$;

-- Pod owner tunes the brain of its own streamers (D108). Edit rules and Wake Up stay admin-only until
-- they carry a pod tag (build plan Phase 1).
drop policy if exists pod_owner_write on public.streamer_brain;
create policy pod_owner_write on public.streamer_brain for all to authenticated
  using (exists (select 1 from public.streamers s
                 where s.id = streamer_brain.streamer_id and public.is_pod_owner(s.pod_id)))
  with check (exists (select 1 from public.streamers s
                      where s.id = streamer_brain.streamer_id and public.is_pod_owner(s.pod_id)));
grant insert, update on public.streamer_brain to authenticated;

revoke execute on function public.is_pod_owner(uuid), public.my_ledger_pod_ids(),
  public.ledger_reverse(uuid, text), public.pod_campaign_set(uuid, uuid, text) from public, anon;
grant execute on function public.is_pod_owner(uuid), public.my_ledger_pod_ids(),
  public.ledger_reverse(uuid, text), public.pod_campaign_set(uuid, uuid, text) to authenticated;

-- Owners added later also become Pod 1 owners (D102: Zo approves Pod 1 as its owner).
create or replace function public.owner_to_pod1() returns trigger
language plpgsql security definer set search_path = public as $f$
begin
  insert into public.pod_members(pod_id, user_id, role)
  values (public.default_pod_id(), new.user_id, 'owner') on conflict do nothing;
  return new;
end $f$;
drop trigger if exists owner_to_pod1 on public.owners;
create trigger owner_to_pod1 after insert on public.owners for each row execute function public.owner_to_pod1();
