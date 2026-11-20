-- Security advisor fixes (D059). Pin search_path on the remaining functions and
-- stop trigger-only functions from being callable through /rest/v1/rpc.
-- Owner-checked RPCs (review_clip, mark_submitted, set_awake, is_owner) stay
-- callable by signed-in users on purpose: each refuses anyone not in owners.
alter function public.current_actor() set search_path = public;
alter function public.clips_guard() set search_path = public;
alter function public.clip_transition_allowed(public.clip_state, public.clip_state, text) set search_path = public;
alter function public.publications_guard() set search_path = public;

revoke execute on function public.clips_audit() from public, anon, authenticated;
revoke execute on function public.publications_open_submission() from public, anon, authenticated;
