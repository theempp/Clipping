-- Judge rubric from the clipper-video plan (P1): 1-10 score, hook type.
-- Review queue sorts best first: score_10 desc, then confidence.
alter table public.clips
  add column if not exists score_10 smallint check (score_10 between 1 and 10),
  add column if not exists hook_type text check (hook_type in
    ('surprising_fact', 'bold_claim', 'story_start', 'reaction_peak', 'play_peak', 'none'));

create index if not exists clips_review_rank_idx
  on public.clips (state, score_10 desc nulls last, confidence desc nulls last);
