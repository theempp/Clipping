# Broadcast dashboard — handoff (2026-11-23)

**Live:** https://zowoagency.com (Vercel project `clipp-dashboard`, root `dashboard/`, team theempp's projects). PR theempp/Clipping#8 merged (910ea53). D097 in Decision Log.

## Done
- SQL checks in CI (`supabase-sql` workflow), green.
- Live Supabase (aqmufpztmzsolpanrgsq): migrations `longform_tiktok`, `live_stats`, `revise_failed` applied and verified (RLS, RPC grants, Realtime).
- Supabase Auth: Site URL https://zowoagency.com, redirect /auth/callback added.
- Vercel env: all keys set (anon key Sensitive off). DNS A @ -> 216.198.79.1 verified.
- PC worker: new Twitch keys verified (token + Helix 200). Kick verified. Worker reads Supabase.
- Code: revise-failed state, snapshot slot dedupe, cron path, real editor cuts (trim+concat), real waveform, note diff, detector reads streamer_brain.

## Next (in order)
1. Zo signs in at zowoagency.com (email code). Then POST `/api/live?force=1` from the signed-in page; read `errors` for twitch/kick/youtube/x (Vercel keys untested until this).
2. Check sign-in + Realtime against real data.
3. Zo adds Vault secret `clipp_cron_secret` (same value as Vercel CRON_SECRET), then run `supabase/snippets/schedule_live_stats.sql` with host zowoagency.com; check `cron.job_run_details`.
4. Real editor test on the PC worker with a live clip (Send -> re-render -> review; also a failing revision shows the red notice).
5. Watch: a `claude/pods` branch deploy had been promoted to production before the merge; don't let it take production again.
