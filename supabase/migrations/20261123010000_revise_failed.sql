-- A revision whose re-render fails QA no longer leaves the clip silently stuck in "revise".
-- The worker writes {rev, reason, at, revisions:[ids]} here and stops retrying those same notes;
-- the dashboard shows it, and Zo can deny the clip. Cleared when a revision passes.
alter table public.clips add column if not exists revise_failed jsonb;
