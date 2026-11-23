-- Trigger-only function; not callable over the API (Supabase advisor 0028). Applied live 2026-11-23.
revoke execute on function public.owner_to_pod1() from public, anon, authenticated;
