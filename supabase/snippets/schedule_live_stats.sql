-- Polls /api/live every minute while no dashboard is open (D093 follow-up). Run once in the SQL editor,
-- AFTER the dashboard is deployed and CRON_SECRET is set on Vercel. Not a migration: it holds a host name.
--
-- 1) Store the same CRON_SECRET in Vault yourself (Dashboard > Vault, name: clipp_cron_secret). Never paste
--    it into this file or a commit.
-- 2) Replace <dashboard-host> below, then run this file.
create extension if not exists pg_cron;
create extension if not exists pg_net;

select cron.unschedule('clipp-live-stats') where exists (select 1 from cron.job where jobname = 'clipp-live-stats');
select cron.schedule('clipp-live-stats', '* * * * *', $$
  select net.http_post(
    url := 'https://<dashboard-host>/api/live',
    headers := jsonb_build_object('Authorization', 'Bearer ' ||
      (select decrypted_secret from vault.decrypted_secrets where name = 'clipp_cron_secret')),
    timeout_milliseconds := 20000)
$$);
-- Check: select * from cron.job_run_details where jobid = (select jobid from cron.job where jobname = 'clipp-live-stats') order by start_time desc limit 5;
