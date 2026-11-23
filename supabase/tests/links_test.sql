-- Paste-a-link checks (20261126000000_link_jobs). Run after core_test.sql (owner aa, streamer lacy).
-- link_key cases: the shared list lives in docs/link_cases.json; run.sh feeds it in as :cases.
select set_config('clipp.cases', :'cases', false) is not null as cases_loaded;
do $$ declare c jsonb; got text; begin
  for c in select * from jsonb_array_elements(current_setting('clipp.cases')::jsonb) loop
    got := public.link_key(c->>0);
    if got is distinct from (c->>1) then
      raise exception 'FAIL: link_key(%) = %, want %', c->>0, got, c->>1; end if;
  end loop;
end $$;

set role authenticated;
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000aa"}', false);
do $$ declare a jsonb; b jsonb; begin
  a := public.request_link_clips('https://www.twitch.tv/videos/2301234567', 'lacy', null, null, 4, false);
  if (a->>'duplicate')::boolean then raise exception 'FAIL: first paste flagged duplicate'; end if;
  if (a->'job'->>'est_usd')::numeric <> 0.01 then raise exception 'FAIL: estimate %', a->'job'->>'est_usd'; end if;
  b := public.request_link_clips('https://twitch.tv/videos/2301234567?t=10s');
  if not (b->>'duplicate')::boolean or b->'job'->>'id' <> a->'job'->>'id' then
    raise exception 'FAIL: same VOD pasted twice made a second job'; end if;
  -- a different range of the same VOD is a new request
  b := public.request_link_clips('https://twitch.tv/videos/2301234567', null, 600, 1200);
  if (b->>'duplicate')::boolean then raise exception 'FAIL: new range flagged duplicate'; end if;
  begin
    perform public.request_link_clips('https://example.com/v.mp4');
    raise exception 'FAIL: unsupported link accepted';
  exception when raise_exception then if sqlerrm like 'FAIL%' then raise; end if; end;
  begin
    perform public.request_link_clips('https://youtu.be/dQw4w9WgXcQ', 'nobody');
    raise exception 'FAIL: unknown streamer accepted';
  exception when raise_exception then if sqlerrm like 'FAIL%' then raise; end if; end;
  begin
    insert into public.link_jobs(url, url_key, platform) values ('x', 'x:1', 'x');
    raise exception 'FAIL: owner inserted a link job directly';
  exception when insufficient_privilege then null; end;
  -- cancel frees the link for a fresh paste
  perform public.cancel_link_job((a->'job'->>'id')::uuid);
  b := public.request_link_clips('https://www.twitch.tv/videos/2301234567', 'lacy');
  if (b->>'duplicate')::boolean then raise exception 'FAIL: canceled link still blocks a new paste'; end if;
  if (select count(*) from public.link_jobs) <> 3 then raise exception 'FAIL: owner cannot read link jobs'; end if;
end $$;
reset role;

-- non-owner sees nothing and cannot request
set role authenticated;
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000bb"}', false);
do $$ begin
  if (select count(*) from public.link_jobs) <> 0 then raise exception 'FAIL: non-owner reads link jobs'; end if;
  begin
    perform public.request_link_clips('https://youtu.be/dQw4w9WgXcQ');
    raise exception 'FAIL: non-owner requested clips';
  exception when raise_exception then if sqlerrm like 'FAIL%' then raise; end if; end;
end $$;
reset role;
select 'LINK SQL CHECKS PASSED';
-- the PC's command-line paste works as service role; owners cannot call it or the shared body
set role service_role;
select set_config('request.jwt.claims', '{"role":"service_role"}', false);
do $$ begin
  if (public.request_link_clips_worker('https://youtu.be/dQw4w9WgXcQ', 'lacy')->>'duplicate')::boolean then
    raise exception 'FAIL: worker paste flagged duplicate'; end if;
end $$;
reset role;
set role authenticated;
select set_config('request.jwt.claims', '{"role":"authenticated","sub":"00000000-0000-0000-0000-0000000000aa"}', false);
do $$ begin
  begin
    perform public._request_link('https://youtu.be/aaaaaaaaaaa', null, null, null, 1, false);
    raise exception 'FAIL: owner called the unchecked body';
  exception when insufficient_privilege then null; end;
end $$;
reset role;
select 'LINK WORKER SQL CHECKS PASSED';
