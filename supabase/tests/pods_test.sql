-- Behavioural checks for the pods + ledger migration (D091-D097). Runs after core_test.sql on the same database.
-- aa = agency admin (owners row), bb = stranger, cc = Pod 2 owner, dd = Pod 2 member.
insert into auth.users values ('00000000-0000-0000-0000-0000000000cc'), ('00000000-0000-0000-0000-0000000000dd');
-- the migration backfills owners into Pod 1; the test owner was created after it ran, so add it the same way
insert into public.pod_members(pod_id, user_id, role)
  select public.default_pod_id(), '00000000-0000-0000-0000-0000000000aa', 'owner' on conflict do nothing;
insert into public.pods(slug, name, status, trial_ends_at) values ('pod-2', 'Pod 2', 'trial', current_date + 90);
insert into public.streamers(slug, display_name, twitch_login, pod_id)
  select 'p2s', 'Pod Two Streamer', 'p2s', id from public.pods where slug = 'pod-2';
insert into public.pod_members(pod_id, user_id, role)
  select id, '00000000-0000-0000-0000-0000000000cc', 'owner' from public.pods where slug = 'pod-2';
insert into public.pod_members(pod_id, user_id, role)
  select id, '00000000-0000-0000-0000-0000000000dd', 'member' from public.pods where slug = 'pod-2';

-- backfill + defaults: every streamer/destination has a pod; core_test clips were tagged Pod 1 from channel_key
do $$ begin
  if (select count(*) from public.pods where slug = 'pod-1') <> 1 then raise exception 'FAIL: pod-1 missing'; end if;
  if exists (select 1 from public.streamers where pod_id is null) then raise exception 'FAIL: streamer without pod'; end if;
  if exists (select 1 from public.destinations where pod_id is null) then raise exception 'FAIL: destination without pod'; end if;
  if (select pod_id from public.clips where job_id = 'job1') is distinct from public.default_pod_id() then
    raise exception 'FAIL: job1 not tagged Pod 1'; end if;
end $$;

-- worker inserts one clip per pod without pod_id; the trigger tags them from the streamer
set role service_role;
select set_config('request.jwt.claims', '{"role":"service_role"}', false);
insert into public.clips(job_id, channel_key, moment_at, state) values
  ('p1job', 'twitch:lacy', now(), 'pending_review'), ('p2job', 'twitch:P2S', now(), 'pending_review');
reset role;
do $$ begin
  if (select p.slug from public.clips c join public.pods p on p.id = c.pod_id where c.job_id = 'p2job') <> 'pod-2' then
    raise exception 'FAIL: p2job not tagged Pod 2'; end if;
end $$;

-- Pod 2 owner sees only Pod 2 and cannot touch Pod 1 clips
set role authenticated;
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000cc"}', false);
do $$ begin
  if public.is_admin() then raise exception 'FAIL: pod owner is admin'; end if;
  if (select count(*) from public.clips) <> 1 then raise exception 'FAIL: pod 2 sees % clips', (select count(*) from public.clips); end if;
  if (select count(*) from public.pods) <> 1 or (select count(*) from public.streamers) <> 1 then
    raise exception 'FAIL: pod 2 sees other pods or streamers'; end if;
  if exists (select 1 from public.clip_events e join public.clips c on c.id = e.clip_id where c.job_id <> 'p2job') then
    raise exception 'FAIL: pod 2 sees Pod 1 audit rows'; end if;
  if (public.my_access()->>'admin')::boolean or jsonb_array_length(public.my_access()->'pods') <> 1 then
    raise exception 'FAIL: my_access %', public.my_access(); end if;
end $$;
do $$ begin
  perform public.review_clip((select id from public.clips c where c.job_id = 'p1job'), 'approve');
  raise exception 'FAIL: pod 2 approved a Pod 1 clip';
exception when raise_exception then
  if sqlerrm like 'FAIL%' then raise; end if;
end $$;
-- the RPC checks the pod, not visibility: pass Pod 1's id directly (looked up as superuser below)
reset role;
select set_config('test.p1job', (select id::text from public.clips where job_id = 'p1job'), false);
set role authenticated;
do $$ begin
  perform public.review_clip(current_setting('test.p1job')::uuid, 'reject');
  raise exception 'FAIL: pod 2 rejected a Pod 1 clip';
exception when raise_exception then
  if sqlerrm like 'FAIL%' then raise; end if;
end $$;
select public.review_clip((select id from public.clips where job_id = 'p2job'), 'approve', 'pod 2 ok');
do $$ begin
  if (select state from public.clips where job_id = 'p2job') <> 'approved' then raise exception 'FAIL: pod 2 approve'; end if;
end $$;
-- pod member cannot write the ledger
do $$ begin
  perform public.ledger_add(public.default_pod_id(), null, 'x', 100);
  raise exception 'FAIL: member added a ledger entry';
exception when raise_exception then
  if sqlerrm like 'FAIL%' then raise; end if;
end $$;
do $$ begin
  insert into public.ledger_entries(pod_id, source_ref, gross_cents) select id, 'direct', 100 from public.pods limit 1;
  raise exception 'FAIL: member inserted a ledger row';
exception when raise_exception or insufficient_privilege then
  if sqlerrm like 'FAIL%' then raise; end if;
end $$;

-- stranger sees nothing
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000bb"}', false);
do $$ begin
  if exists (select 1 from public.pods) or exists (select 1 from public.clips) or exists (select 1 from public.campaigns) then
    raise exception 'FAIL: stranger sees pod data'; end if;
end $$;

-- admin sees every pod and runs the ledger: pending -> cleared -> approved -> paid, nothing skipped
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000aa"}', false);
do $$ begin
  if (select count(*) from public.pods) <> 2 then raise exception 'FAIL: admin pods'; end if;
  if not exists (select 1 from public.clips where job_id = 'p2job') then raise exception 'FAIL: admin cannot see pod 2'; end if;
end $$;
select public.ledger_add((select id from public.pods where slug = 'pod-2'), null, 'cr-1', 10001, 'first payout');
select public.ledger_add((select id from public.pods where slug = 'pod-2'), null, 'cr-2', 500);
do $$ declare e public.ledger_entries; begin
  select * into e from public.ledger_entries where source_ref = 'cr-1';
  if e.agency_rate <> 0.15 or e.agency_cut_cents <> 1500 or e.pod_net_cents <> 8501 or e.status <> 'pending' then
    raise exception 'FAIL: split % % % %', e.agency_rate, e.agency_cut_cents, e.pod_net_cents, e.status; end if;
  if e.created_by <> '00000000-0000-0000-0000-0000000000aa' then raise exception 'FAIL: created_by'; end if;
end $$;
do $$ begin
  begin
    perform public.ledger_add((select id from public.pods where slug = 'pod-2'), null, 'cr-1', 1);
    raise exception 'FAIL: duplicate payout ref';
  exception when unique_violation then null; end;
  begin
    perform public.ledger_set_status((select id from public.ledger_entries where source_ref = 'cr-1'), 'approved');
    raise exception 'FAIL: approved before cleared';
  exception when raise_exception then if sqlerrm like 'FAIL%' then raise; end if; end;
end $$;
select public.ledger_set_status((select id from public.ledger_entries where source_ref = 'cr-1'), 'cleared');
do $$ begin
  perform public.ledger_set_status((select id from public.ledger_entries where source_ref = 'cr-1'), 'paid', 'bank-1');
  raise exception 'FAIL: paid before approved';
exception when raise_exception then
  if sqlerrm like 'FAIL%' then raise; end if;
end $$;
select public.ledger_set_status((select id from public.ledger_entries where source_ref = 'cr-1'), 'approved');
do $$ begin
  perform public.ledger_set_status((select id from public.ledger_entries where source_ref = 'cr-1'), 'paid', '  ');
  raise exception 'FAIL: paid without a transfer reference';
exception when raise_exception then
  if sqlerrm like 'FAIL%' then raise; end if;
end $$;
select public.ledger_set_status((select id from public.ledger_entries where source_ref = 'cr-1'), 'paid', 'bank-1');
do $$ declare e public.ledger_entries; begin
  select * into e from public.ledger_entries where source_ref = 'cr-1';
  if e.cleared_at is null or e.approved_by <> '00000000-0000-0000-0000-0000000000aa'
     or e.paid_by <> '00000000-0000-0000-0000-0000000000aa' or e.paid_ref <> 'bank-1' then
    raise exception 'FAIL: ledger stamps'; end if;
  begin
    perform public.ledger_set_status(e.id, 'pending');
    raise exception 'FAIL: paid entry moved';
  exception when raise_exception then if sqlerrm like 'FAIL%' then raise; end if; end;
end $$;
reset role;

-- worker (service role) cannot move a ledger status; nobody deletes or rewrites history
set role service_role;
select set_config('request.jwt.claims', '{"role":"service_role"}', false);
do $$ begin
  update public.ledger_entries set status = 'cleared' where source_ref = 'cr-2';
  raise exception 'FAIL: worker changed ledger status';
exception when raise_exception then
  if sqlerrm like 'FAIL%' then raise; end if;
end $$;
reset role;
select set_config('request.jwt.claims', '', false);
do $$ begin
  begin delete from public.ledger_entries where source_ref = 'cr-2'; raise exception 'FAIL: ledger delete';
  exception when raise_exception then if sqlerrm like 'FAIL%' then raise; end if; end;
  begin update public.ledger_events set actor = 'x'; raise exception 'FAIL: audit update';
  exception when raise_exception then if sqlerrm like 'FAIL%' then raise; end if; end;
  begin delete from public.ledger_events; raise exception 'FAIL: audit delete';
  exception when raise_exception then if sqlerrm like 'FAIL%' then raise; end if; end;
  begin truncate public.ledger_events; raise exception 'FAIL: audit truncate';
  exception when raise_exception then if sqlerrm like 'FAIL%' then raise; end if; end;
  if (select count(*) from public.ledger_events v join public.ledger_entries e on e.id = v.entry_id
      where e.source_ref = 'cr-1') <> 4 then raise exception 'FAIL: expected 4 ledger audit rows'; end if;
end $$;

-- Pod 2 reads its own ledger and statement, read-only; Pod 1 sees none of it
set role authenticated;
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000dd"}', false);
do $$ begin
  if (select count(*) from public.ledger_entries) <> 2 then raise exception 'FAIL: pod 2 ledger rows'; end if;
  if (select sum(paid_net_cents) from public.pod_statements) <> 8501
     or (select sum(pending_net_cents) from public.pod_statements) <> 425 then
    raise exception 'FAIL: statement totals'; end if;
  update public.ledger_entries set gross_cents = 1;
  if found then raise exception 'FAIL: member updated the ledger'; end if;
end $$;
do $$ begin
  perform public.ledger_set_status((select id from public.ledger_entries where source_ref = 'cr-2'), 'cleared');
  raise exception 'FAIL: member moved a ledger status';
exception when raise_exception then
  if sqlerrm like 'FAIL%' then raise; end if;
end $$;
reset role;
-- a Pod 1-only member (not admin) sees no Pod 2 money
insert into auth.users values ('00000000-0000-0000-0000-0000000000ee');
insert into public.pod_members(pod_id, user_id, role) values (public.default_pod_id(), '00000000-0000-0000-0000-0000000000ee', 'member');
set role authenticated;
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000ee"}', false);
do $$ begin
  if exists (select 1 from public.ledger_entries) or exists (select 1 from public.pod_statements)
     or exists (select 1 from public.clips where job_id = 'p2job') then
    raise exception 'FAIL: Pod 1 member sees Pod 2 data'; end if;
end $$;
reset role;
select 'ALL POD CHECKS PASSED';
