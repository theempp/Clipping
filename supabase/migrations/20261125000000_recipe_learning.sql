-- D114: each reviewed clip teaches the editing recipe weights once.
alter table public.clips add column if not exists recipe_learned_at timestamptz;
