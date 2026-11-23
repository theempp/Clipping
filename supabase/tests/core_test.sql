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

-- Wake Up control (D055): owner flips it, non-owner cannot, worker reads it.
set role authenticated;
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000bb"}', false);
do $$ begin
  perform public.set_awake(true);
  raise exception 'FAIL: non-owner woke the worker';
exception when raise_exception then
  if sqlerrm like 'FAIL%' then raise; end if;
end $$;
do $$ begin
  if exists (select 1 from public.control) then raise exception 'FAIL: RLS leaked control to non-owner'; end if;
  if public.is_owner() then raise exception 'FAIL: non-owner is_owner'; end if;
end $$;
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000aa"}', false);
select public.set_awake(true);
do $$ begin
  if not (select awake from public.control) then raise exception 'FAIL: owner could not wake'; end if;
  if (select updated_by from public.control) <> '00000000-0000-0000-0000-0000000000aa' then
    raise exception 'FAIL: wake not attributed'; end if;
end $$;
-- revision from the plain-English box: kind other, note = text, empty payload
reset role;
set role service_role;
select set_config('request.jwt.claims', '{"role":"service_role"}', false);
insert into public.clips(job_id, channel_key, moment_at, state) values ('job2', 'twitch:lacy', now(), 'pending_review');
reset role;
set role authenticated;
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000aa"}', false);
select public.review_clip((select id from public.clips where job_id = 'job2'), 'revise', 'cut the first two seconds', 'other', '{}');
do $$ begin
  if not exists (select 1 from public.revisions r join public.clips c on c.id = r.clip_id
                 where c.job_id = 'job2' and r.kind = 'other' and r.note = 'cut the first two seconds'
                 and r.payload = '{}' and c.state = 'revise') then
    raise exception 'FAIL: revision box row wrong'; end if;
end $$;
reset role;
-- long-form TikTok (D075-D078): post only after approval; stats roll up per test cell
set role service_role;
select set_config('request.jwt.claims', '{"role":"service_role"}', false);
insert into public.clips(job_id, channel_key, moment_at, state, category)
  values ('long-p1', 'twitch:lacy', now(), 'pending_review', 'longform');
insert into public.longform_videos(id, clip_id, format, pacing, caption_style, voice, layout, runtime_s)
  values ('p1', (select id from public.clips where job_id = 'long-p1'), 'recap', 'short', 'A', 'ai', 'switch', 72);
do $$ begin
  begin
    insert into public.longform_videos(id, format, pacing, caption_style, voice, layout, runtime_s)
      values ('p2', 'recap', 'short', 'A', 'ai', 'switch', 58);
    raise exception 'FAIL: sub-minute long video accepted';
  exception when check_violation then null; end;
end $$;
reset role;
set role authenticated;
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000aa"}', false);
do $$ begin
  begin
    perform public.mark_tiktok_posted('p1', 'https://www.tiktok.com/@zwoclipp/video/1');
    raise exception 'FAIL: unapproved video marked posted';
  exception when raise_exception then
    if sqlerrm like 'FAIL%' then raise; end if;
  end;
end $$;
select public.review_clip((select id from public.clips where job_id = 'long-p1'), 'approve');
select public.mark_tiktok_posted('p1', 'https://www.tiktok.com/@zwoclipp/video/1');
insert into public.tiktok_stats(video_id, views, follows, qualified_views, rewards_usd, avg_watch_s)
  values ('p1', 10000, 50, 8000, 4.40, 31);
do $$ begin
  if (select follows_per_1k from public.longform_results where format = 'recap') <> 5.00 then
    raise exception 'FAIL: follows per 1k wrong'; end if;
  if (select rpm_usd from public.longform_results where format = 'recap') <> 0.55 then
    raise exception 'FAIL: rpm wrong'; end if;
end $$;
reset role;

-- live_stats migration (D092/D093)
set role authenticated;
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000bb"}', false);
do $$ begin
  perform public.set_brain_weights((select id from public.streamers where slug = 'lacy'), '{"chat_spike":1}');
  raise exception 'FAIL: non-owner set brain weights';
exception when raise_exception then
  if sqlerrm like 'FAIL%' then raise; end if;
end $$;
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000aa"}', false);
-- first save of one slider keeps the other defaults; junk, null, out-of-range and unknown keys handled
select public.set_brain_weights((select id from public.streamers where slug = 'lacy'),
  '{"chat_spike":"150","voice_peak":null,"chat_words":"abc","viewer_clips":12.6,"bogus":5}', array['  Clip ', 'clip', '', 'W']);
do $$ declare b public.streamer_brain; begin
  select * into b from public.streamer_brain limit 1;
  if b.weights <> '{"chat_spike":100,"voice_peak":55,"chat_words":75,"viewer_clips":13,"approved_match":60}'::jsonb then
    raise exception 'FAIL: brain weights %', b.weights; end if;
  if b.words <> array['clip', 'w'] then raise exception 'FAIL: brain words %', b.words; end if;
end $$;
select public.set_brain_weights((select id from public.streamers where slug = 'lacy'), '{"approved_match":-4}');
do $$ begin
  if (select weights->>'approved_match' from public.streamer_brain) <> '0'
     or (select weights->>'chat_spike' from public.streamer_brain) <> '100'
     or (select cardinality(words) from public.streamer_brain) <> 2 then
    raise exception 'FAIL: brain update merge'; end if;
end $$;
-- TikTok: blank keeps the last number, negatives refused, snapshots written
select public.set_manual_stat(1200, 50000, 30);
select public.set_manual_stat(1300, null, null);
do $$ begin
  if not exists (select 1 from public.live_stats where key = 'tiktok:own'
                 and followers = 1300 and views = 50000 and posts = 30) then
    raise exception 'FAIL: tiktok blank wiped a value'; end if;
  if (select count(*) from public.stat_snapshots where key = 'tiktok:own') <> 4 then
    raise exception 'FAIL: tiktok snapshots'; end if;
end $$;
do $$ begin
  perform public.set_manual_stat(-1, null, null);
  raise exception 'FAIL: negative tiktok count accepted';
exception when raise_exception then
  if sqlerrm like 'FAIL%' then raise; end if;
end $$;
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000bb"}', false);
do $$ begin
  if exists (select 1 from public.live_stats) or exists (select 1 from public.stat_snapshots)
     or exists (select 1 from public.streamer_brain) then
    raise exception 'FAIL: non-owner reads live tables'; end if;
end $$;
reset role;
do $$ begin
  if (select count(*) from pg_publication_tables where pubname = 'supabase_realtime' and tablename in ('live_stats', 'streamer_brain')) <> 2 then
    raise exception 'FAIL: realtime publication'; end if;
end $$;
reset role;
-- snapshot slots: a second poller in the same bucket is a no-op; manual (null slot) rows never collide
insert into public.stat_snapshots(key, metric, value, slot) values ('x:own', 'followers', 1, 42)
  on conflict (key, metric, slot) do nothing;
insert into public.stat_snapshots(key, metric, value, slot) values ('x:own', 'followers', 2, 42)
  on conflict (key, metric, slot) do nothing;
do $$ begin
  if (select count(*) from public.stat_snapshots where key = 'x:own') <> 1 then
    raise exception 'FAIL: duplicate snapshot in one slot'; end if;
  if not exists (select 1 from information_schema.columns where table_name = 'clips' and column_name = 'revise_failed') then
    raise exception 'FAIL: clips.revise_failed missing'; end if;
end $$;
select 'ALL SQL CHECKS PASSED';
