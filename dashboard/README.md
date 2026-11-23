# Zwoclippe dashboard

The private review console. Design is **Halo Pro** (D116; source `dashboard-concepts/zwoclippe-halo-final/`): live streamer cards on the left, the top pick in the middle (9:16 player, chat heat, Grok score, headline, Approve / Revise / Reject, **Edit clip**, post toggles), the queue on the right (each clip opens a review popup), and AI spend, today's pipeline, the next 24 h of posts and channel growth along the bottom. Live, Pods & ledger and Stats keep their content inside the same frame.

There is no Wake Up switch any more: the dashboard and the worker are always on (D116 supersedes D055).

**Posting always asks first.** Approve only marks a clip ready. Post needs an approved clip and at least one platform, then a confirm dialog, then a 4-second undo. Only then does the dashboard call `review_clip(approve)`, which is what the PC's publisher reads. Edit clip opens the editor (Trim, Captions, Headline, Crop, Flashback, Audio; no zoom, D112); Save sends only what changed as a revision, the PC re-renders it, and the learn loop logs it as a manual edit (D114).

On desktop (1181 px wide and 701 px tall and up) the console fills the screen with no page scroll; below that it stacks and scrolls.

## Daily launch on Zo's PC

Use the maintained checkout at `C:\clip-work\Clipping`, on `main`. Double-click
`Start Dashboard.cmd` in that checkout, then open http://localhost:3000 after
the terminal says Ready. Keep the terminal open while using the dashboard.
If the dashboard is already running, use the existing server instead of
starting another one on a different port.


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
- **Approve** the top pick, pick platforms, press **Post**, then confirm. The bar at the bottom gives 4 seconds to **Undo**; in demo the clip "posts" a few seconds later.
- **Edit clip**: drag the trim handles, change captions or the headline, then **Save changes**. The clip comes back as the top pick tagged "Edited by you", re-renders (5 s in demo) and can be posted.
- Click any clip in the queue for the review popup. **Post batch** posts every approved clip after one confirm.
- **/** focuses search; **Esc** closes popups.

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
- Postgres decides who sees data: row-level security lets only users in `owners` read anything, and the only writes are owner-checked functions such as `review_clip`, `mark_submitted` and `request_clip`, which check `is_owner()` again. A signed-in stranger sees "Not allowed" and an empty database.
- Sign-in is by email link with sign-ups turned off, so nobody can create an account.
- Clips stay in a private Storage bucket. The dashboard asks for a signed link that expires after 1 hour each time it plays or downloads a clip.

**Pods (`NEXT_PUBLIC_CLIPP_PODS=1`, needs migration `20261124000000_pods.sql`).** The gate calls `my_access()` instead of `is_owner()`. The admin (Zo) sees every pod and picks one in the top bar (All by default); a pod login is pinned to its pod and RLS returns only that pod's rows. Approve, revise and deny show only to the owner of the clip's pod; untagged clips stay admin-only (D102, D103). `review_clip` refuses everyone else anyway. New member = add the user by hand in Supabase Auth plus a `pod_members` row (sign-ups stay off). Demo mode previews a pod login with `?as=pod-2` (owner) or `?as=pod-2&role=member`.
`NEXT_PUBLIC_CLIPP_POD_HOME=1` turns Overview into the pod's action list (stuck posts, to approve, campaigns to join, earnings). Ledger (admin only) records payouts through `ledger_add` / `ledger_set_status` / `ledger_reverse`; the database computes the 15% cut and pod net and allows only pending -> cleared -> approved -> paid. Statements are read-only per pod. The dashboard never moves money (D092).

## Always on

The worker watches and clips whenever it runs; nothing in the dashboard can pause it (D116). The badge in the top bar and the line in the bottom-left come from the PC's own heartbeat, so they say "PC offline" when it stops reporting. The old `control` table and `set_awake` function stay in the database for older dashboards but nothing reads them.

## Platform picking (migration `20261127000000_post_platforms.sql`, not applied yet)

The post toggles save the picked platforms on the clip (`clips.post_platforms`) and the publisher posts only there. Until that migration is applied the toggles are locked on and the confirm dialog says every connected account gets the post, which is what the publisher does today. Platforms without an active `destinations` row are greyed out; TikTok stays a by-hand upload (D074).

## Checks

```powershell
npm test        # logic tests (queue order, countdown, PC state, revision text, review-page numbers)
npm run lint    # TypeScript
npm run build   # production build
```
