-- Halo Pro dashboard (D116): Zo picks the platforms when confirming a post.
-- Additive only. Applied to the clipp project 2026-11-23 on Zo's go-ahead.
--
-- clips.post_platforms: platforms picked in the post confirm dialog ('youtube', 'x', ...).
--   null = older clips / not picked = every active destination (the publisher's old behaviour).
-- review_clip(): same checks and states as the pods version; on 'approve' it also stores
--   p_payload->'platforms' when given. Approve still only happens after the dashboard's
--   confirm dialog, and the publisher still reads only approved clips (D003/D004).
-- control / set_awake (D055) stay in place so older dashboards keep working, but nothing
--   reads them any more: the worker is always on.

alter table public.clips add column if not exists post_platforms text[];

create or replace function public.review_clip(p_clip uuid, p_action text, p_note text default null,
                                              p_kind text default 'other', p_payload jsonb default '{}')
returns public.clips language plpgsql security definer set search_path = public as $$
declare r public.clips; v_pod uuid; v_platforms text[];
begin
  select pod_id into v_pod from public.clips where id = p_clip;
  if not ((v_pod is not null and public.is_pod_owner(v_pod)) or (v_pod is null and public.is_admin())) then
    raise exception 'not allowed';
  end if;
  if p_action not in ('approve', 'revise', 'reject') then raise exception 'bad action %', p_action; end if;
  if p_action = 'revise' and coalesce(p_note, '') = '' then raise exception 'revise needs a note'; end if;
  if p_action = 'approve' and jsonb_typeof(p_payload -> 'platforms') = 'array' then
    select coalesce(array_agg(distinct lower(x)), '{}') into v_platforms
    from jsonb_array_elements_text(p_payload -> 'platforms') as t(x)
    where lower(x) in ('youtube', 'x', 'tiktok');
    if cardinality(v_platforms) = 0 then raise exception 'pick at least one platform'; end if;
  end if;
  perform set_config('app.reason', coalesce(p_note, p_action), true);
  update public.clips set state = case p_action when 'approve' then 'approved'::public.clip_state
                                                when 'revise' then 'revise'::public.clip_state
                                                else 'rejected'::public.clip_state end,
                          post_platforms = case when p_action = 'approve' and v_platforms is not null
                                                then v_platforms else post_platforms end
  where id = p_clip returning * into r;
  if r.id is null then raise exception 'clip % not found', p_clip; end if;
  if p_action = 'revise' then
    insert into public.revisions(clip_id, kind, note, payload, created_by)
    values (p_clip, p_kind, p_note, p_payload, auth.uid());
  end if;
  return r;
end $$;
revoke execute on function public.review_clip(uuid, text, text, text, jsonb) from public, anon;
grant execute on function public.review_clip(uuid, text, text, text, jsonb) to authenticated;
