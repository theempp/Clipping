-- D077/D078 (Zo, 2026-11-22): before/after review and revision memory.

-- Before/after: the untouched 16:9 window next to the vertical clip.
alter table public.clips add column if not exists source_path text;
-- Set by the worker while it re-edits a clip already in review with a learned rule;
-- the dashboard hides the clip until the fixed version is uploaded.
alter table public.clips add column if not exists fixing jsonb;

-- Revision memory: when the worker has read a note for standing rules.
alter table public.revisions add column if not exists learned_at timestamptz;

-- Standing edit rules learned from Zo's revision notes. Every later render applies them,
-- and clips already waiting in review that break one are re-edited before Zo sees them.
create table if not exists public.edit_rules (
  id uuid primary key default gen_random_uuid(),
  key text not null check (key in ('zoom', 'zoom_style', 'sfx', 'caption_colour', 'max_len_s')),
  value jsonb not null,
  label text not null,                 -- plain English, shown on the dashboard
  note text not null,                  -- Zo's own words it came from
  revision_id uuid references public.revisions(id) on delete set null,
  clip_id uuid references public.clips(id) on delete set null,
  active boolean not null default true,
  fixed_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists edit_rules_active_idx on public.edit_rules(key, created_at desc) where active;
alter table public.edit_rules enable row level security;
create policy owner_read on public.edit_rules for select to authenticated using (public.is_owner());

-- Zo can switch a learned rule off (or back on) from the dashboard; nothing else.
create or replace function public.set_rule_active(p_rule uuid, p_on boolean)
returns public.edit_rules language plpgsql security definer set search_path = public as $$
declare r public.edit_rules;
begin
  if not public.is_owner() then raise exception 'not allowed'; end if;
  update public.edit_rules set active = p_on, updated_at = now() where id = p_rule returning * into r;
  return r;
end $$;
revoke execute on function public.set_rule_active(uuid, boolean) from public, anon;
grant execute on function public.set_rule_active(uuid, boolean) to authenticated;

alter publication supabase_realtime add table public.edit_rules;
