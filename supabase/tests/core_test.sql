-- Behavioural checks for the core migration. Run after stub + migrations; any failure raises.
grant select, insert, update, delete on all tables in schema public to service_role, authenticated;
insert into auth.users values ('00000000-0000-0000-0000-0000000000aa'), ('00000000-0000-0000-0000-0000000000bb');
insert into public.owners values ('00000000-0000-0000-0000-0000000000aa');
insert into public.streamers(slug, display_name, twitch_login) values ('lacy', 'Lacy', 'lacy');
insert into public.campaigns(title, status, streamer_slugs) values ('Lacy test', 'active', '{lacy}');
insert into public.destinations(platform, label, credential_ref) values ('youtube', 'main', 'YT_MAIN');

-- worker inserts a clip
set role service_role;
select set_config('request.jwt.claims', '{"role":"service_role"}', false);
insert into public.clips(job_id, channel_key, moment_at, campaign_id)
  select 'job1', 'twitch:lacy', now(), id from public.campaigns limit 1;

-- worker may NOT approve
do $$ begin
  update public.clips set state = 'approved' where job_id = 'job1';
  raise exception 'FAIL: worker approved a clip';
exception when raise_exception then
  if sqlerrm like 'FAIL%' then raise; end if;
end $$;

-- publication before approval refused
do $$ begin
  insert into public.publications(clip_id, destination_id)
    select c.id, d.id from public.clips c, public.destinations d where c.job_id = 'job1';
  raise exception 'FAIL: publication before approval';
exception when raise_exception then
  if sqlerrm like 'FAIL%' then raise; end if;
end $$;
reset role;

-- non-owner human cannot review
set role authenticated;
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000bb"}', false);
do $$ begin
  perform public.review_clip((select id from public.clips where job_id = 'job1'), 'approve');
  raise exception 'FAIL: non-owner reviewed';
exception when raise_exception then
  if sqlerrm like 'FAIL%' then raise; end if;
end $$;
do $$ begin
  if (select count(*) from public.clips) <> 0 then raise exception 'FAIL: RLS leaked clips to non-owner'; end if;
end $$;

-- owner approves
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000aa"}', false);
select public.review_clip((select id from public.clips where job_id = 'job1'), 'approve', 'looks good');
-- human cannot publish directly
do $$ begin
  update public.clips set state = 'published' where job_id = 'job1';
  if found then raise exception 'FAIL: human update succeeded'; end if;
exception when raise_exception or insufficient_privilege then
  if sqlerrm like 'FAIL%' then raise; end if;
end $$;
reset role;

-- worker schedules, posts, publishes
set role service_role;
select set_config('request.jwt.claims', '{"role":"service_role"}', false);
select public.worker_transition((select id from public.clips where job_id = 'job1'), 'scheduled', 'publisher picked up');
insert into public.publications(clip_id, destination_id, status, url, posted_at)
  select c.id, d.id, 'posted', 'https://youtube.com/shorts/x', now() from public.clips c, public.destinations d where c.job_id = 'job1';
select public.worker_transition((select id from public.clips where job_id = 'job1'), 'published');
reset role;

do $$ declare n int; s text; secs int; begin
  select count(*) into n from public.clip_events e join public.clips c on c.id = e.clip_id where c.job_id = 'job1';
  if n <> 4 then raise exception 'FAIL: expected 4 audit rows, got %', n; end if;
  if not exists (select 1 from public.clip_events where to_state = 'approved' and actor = 'human'
                 and reason = 'looks good' and actor_id = '00000000-0000-0000-0000-0000000000aa') then
    raise exception 'FAIL: approval audit row wrong'; end if;
  select status, seconds_left into s, secs from public.submissions_live;
  if s <> 'open' or secs not between 1700 and 1800 then raise exception 'FAIL: countdown % %', s, secs; end if;
  -- duplicate publication row refused (idempotency)
  begin
    insert into public.publications(clip_id, destination_id)
      select c.id, d.id from public.clips c, public.destinations d where c.job_id = 'job1';
    raise exception 'FAIL: duplicate publication';
  exception when unique_violation then null; end;
end $$;
select 'ALL SQL CHECKS PASSED';
