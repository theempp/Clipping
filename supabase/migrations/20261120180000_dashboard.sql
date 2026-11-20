-- Dashboard v1 (D053-D058): Wake Up control, streamer avatars, owner check RPC.

-- Wake Up (D055). One row. Zo flips it from the dashboard; the worker reads it
-- every heartbeat and only watches streams while it is on. The dashboard shows
-- the worker's own heartbeat next to it, so the switch never fakes a running PC.
create table public.control (
  id boolean primary key default true check (id),
  awake boolean not null default false,
  updated_at timestamptz not null default now(),
  updated_by uuid references auth.users(id)
);
insert into public.control(id) values (true) on conflict do nothing;

alter table public.control enable row level security;
create policy owner_read on public.control for select to authenticated using (public.is_owner());

create or replace function public.set_awake(p_on boolean)
returns public.control language plpgsql security definer set search_path = public as $$
declare r public.control;
begin
  if not public.is_owner() then raise exception 'not allowed'; end if;
  update public.control set awake = p_on, updated_at = now(), updated_by = auth.uid()
  where id returning * into r;
  return r;
end $$;
revoke execute on function public.set_awake(boolean) from public, anon;
grant execute on function public.set_awake(boolean) to authenticated;

-- Lets the login page tell "signed in but not the owner" apart from "no data yet".
revoke execute on function public.is_owner() from public, anon;
grant execute on function public.is_owner() to authenticated;

-- Optional avatar for the rail; initials are shown when empty.
alter table public.streamers add column if not exists avatar_url text;

alter publication supabase_realtime add table public.control;
