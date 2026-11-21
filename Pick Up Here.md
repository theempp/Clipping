# Pick up here (2026-11-20, evening)

## Where things stand
- Dashboard is wired to the real Supabase project `clipp` (ref `aqmufpztmzsolpanrgsq`, us-east-1). Zo signed in on the PC at 7:31 PM on 2026-11-20.
- Code: PR #4 (branch `claude/project-thread-646sy2`), stacked on #3, #2, #1. CI green, nothing merged to main.
- Decisions D059-D063 in [[Decision Log]]. Next free ID: D064.
- The older Supabase project supabase-cyan-notebook is paused (free-tier cap). Restore it from the Supabase dashboard if that app is needed.

## Running the dashboard on the PC
- Code lives in `C:\clip-work\Clipping` (a clone of the PR #4 branch, not this vault).
- Start: PowerShell, `cd C:\clip-work\Clipping\dashboard`, `npm run dev`, then open http://localhost:3000. Closing that window stops it.
- `.env.local` there holds the Supabase URL and the public anon key only.

## Logging in
- Request the link at localhost:3000/login on the PC, then open the email at icloud.com/mail **in the same Chrome on the PC**. Links opened on the phone fail (localhost = the phone).
- Supabase's built-in mailer sends about 2 emails an hour.
- The 6-digit code sign-in (D063) needs a custom SMTP sender (e.g. Resend), because the email template is locked on the built-in mailer.

## Open items
1. Delete or Deny the 3 `seed-*` test clips in the queue.
2. Optional: set up Resend SMTP so login works from the phone.
3. Worker `.env` on the PC: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (from Supabase > Project Settings > API keys), plus Twitch/Kick/Grok/YouTube/X keys.
4. Review and merge PRs #1-#4 in order.
5. Zo's new focus: clipping GTA 6 (raised 2026-11-20, not planned yet).
