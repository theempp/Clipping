# Clipp dashboard (v1)

The private review dashboard for Clipp: review queue sorted by score, 9:16 clip player, Deny / Revise / Approve, the plain-English revision box, the 30-minute Content Rewards countdown, the Wake Up switch, and a Cinema live page per streamer. Design is the Stage direction (D049); decisions D053-D058 are in the vault Decision Log.

It works on a computer and a phone. On a phone the streamer rail becomes an avatar strip at the top and the Deny / Revise / Approve buttons stay pinned to the bottom.

## Daily launch on Zo's PC

Use the maintained checkout at `C:\clip-work\Clipping`, on `main`. Double-click
`Start Dashboard.cmd` in that checkout, then open http://localhost:3000 after
the terminal says Ready. Keep the terminal open while using the dashboard.
If the dashboard is already running, use the existing server instead of
starting another one on a different port.

The November 22 dashboard update includes before/after review, weekly stats,
revision memory, and the updated Wake Up control. The `v1` label is the app's
release label, not an indication that the old dashboard is running.

Do not launch a copied `dashboard-active` folder. Update `main` in the maintained
checkout before starting it. The Desktop path includes `HOME!`; Webpack rejects
the exclamation mark, so the running app must stay under `C:\clip-work`.

## See it on your PC in 2 minutes (demo mode, Windows 11)

Demo mode uses sample clips that ship with the app. It needs no Supabase, no keys and no worker, and nothing you click is saved or posted.

1. Install **Node.js 22 LTS** from https://nodejs.org (the Windows Installer, default options).
2. Open **PowerShell** and go to the dashboard folder of the repo, for example:
   ```powershell
   cd C:\clip-work\Clipping\dashboard
   ```
3. Install and start:
   ```powershell
   npm install
   npm run demo
   ```
4. Open http://localhost:3000 in your browser.

To see the phone layout, open the same address on your phone while it is on the same Wi-Fi, using the PC's address instead of `localhost` (for example `http://192.168.1.20:3000`; `ipconfig` shows it as "IPv4 Address"). Windows may ask to allow Node.js through the firewall; allow it on private networks.

Things to try:
- **A**, **D**, **R** keys approve, deny, or open the revision box. Approve and Deny wait 4 seconds with an **Undo** button before they count.
- The **Wake Up** switch (top right) puts the whole page to sleep and wakes it again.
- Click a streamer in the left rail to open their Cinema live page.
- **Save** under "Approved · ready on phone" downloads the clip.

Stop the server with **Ctrl+C**.

## Run it against the real database

### 1. Supabase project (one time)

> Done for Clipp (D059-D062): project `clipp` (`https://aqmufpztmzsolpanrgsq.supabase.co`), all migrations applied, `clips` bucket private, owner row is added automatically when the owner login is created. Only steps 3, 4 and 6 below are left to click.

1. Create a project at https://supabase.com.
2. Run the SQL files in `supabase/migrations/` in order (SQL Editor, paste each file, Run), or `supabase db push` with the Supabase CLI.
3. **Authentication > Sign In / Providers**: keep Email on, turn **off** "Allow new users to sign up".
4. **Authentication > Users > Add user > Send invitation** to your own email. Accept the invite.
5. Make yourself the owner. In the SQL Editor:
   ```sql
   insert into public.owners(user_id)
   select id from auth.users where email = 'YOUR EMAIL';
   ```
6. **Authentication > Emails > Magic Link**: add `Code: {{ .Token }}` to the template so you can sign in by code on any device (D063).
7. **Authentication > URL Configuration**: set Site URL to your dashboard address and add `http://localhost:3000/auth/callback` and `https://<your-vercel-domain>/auth/callback` to Redirect URLs.

### 2. Keys on the PC

Copy `.env.example` to `.env.local` in this folder and fill in the two public values from **Project Settings > API**:

```
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon / publishable key>
```

Only the anon (publishable) key goes here. The service-role key belongs to the worker's `.env` and must never reach the browser. `.env.local` is git-ignored.

**Live numbers (optional, server-only).** `POST /api/live` polls Twitch, Kick, YouTube and X and writes `live_stats`. It runs only on the server and needs these variables without a `NEXT_PUBLIC_` prefix (names are in `.env.example`; values never go in git, notes or screenshots):

| Variable | Used for |
| --- | --- |
| `SUPABASE_SERVICE_ROLE_KEY` | server-side writes to `live_stats`, `stat_snapshots`, streamer avatars |
| `CRON_SECRET` | lets a scheduler call `/api/live` with `Authorization: Bearer …` |
| `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET` | Helix live status, viewers, avatars |
| `KICK_CLIENT_ID`, `KICK_CLIENT_SECRET` | Kick live status, viewers, avatars |
| `YOUTUBE_API_KEY`, `YOUTUBE_CHANNEL_ID` | own YouTube channel numbers |
| `X_BEARER_TOKEN`, `X_USERNAME` | own X account numbers |

A source with a missing variable is skipped and shows "key not set"; one failing source never blanks the others. The open dashboard polls about once a minute; nothing polls while it is closed unless a scheduler calls `/api/live`. TikTok stays manual until the API audit. Requires the `live_stats` migration.

```powershell
npm run dev
```

Open http://localhost:3000, enter your email, and click the link in the email on the same device.

### 3. Vercel (phone access from anywhere)

1. Import the GitHub repo in Vercel and set **Root Directory** to `dashboard`.
2. Add the same two `NEXT_PUBLIC_SUPABASE_*` variables under Project Settings > Environment Variables.
3. Deploy, then add the Vercel address to Supabase Redirect URLs (step 1.7).
4. On the phone, open the site and use **Add to Home Screen**.

## How access is protected

- Every page except `/login` needs a signed-in session (middleware).
- Postgres decides who sees data: row-level security lets only users in `owners` read anything, and the only writes are the `review_clip`, `mark_submitted` and `set_awake` functions, which check `is_owner()` again. A signed-in stranger sees "Not allowed" and an empty database.
- Sign-in is by email link with sign-ups turned off, so nobody can create an account.
- Clips stay in a private Storage bucket. The dashboard asks for a signed link that expires after 1 hour each time it plays or downloads a clip.

## Wake Up

The switch records what you want in the `control` table. The worker on the PC reads it every 15 seconds:
- **On**: it watches live streams and clips them.
- **Off**: it stops watching and capturing. Clips already rendering, waiting for review or posting still finish.

The small line under the switch is what the PC itself last reported (watching, awake, waking up, offline and when it was last seen), so the switch never pretends the PC is running when it is off.

## Checks

```powershell
npm test        # logic tests (queue order, countdown, PC state, revision text)
npm run lint    # TypeScript
npm run build   # production build
```
