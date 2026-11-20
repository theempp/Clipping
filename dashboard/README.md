# Clipp dashboard (v1)

The private review dashboard for Clipp: review queue sorted by score, 9:16 clip player, Deny / Revise / Approve, the plain-English revision box, the 30-minute Content Rewards countdown, the Wake Up switch, and a Cinema live page per streamer. Design is the Stage direction (D049); decisions D053-D058 are in the vault Decision Log.

It works on a computer and a phone. On a phone the streamer rail becomes an avatar strip at the top and the Deny / Revise / Approve buttons stay pinned to the bottom.

## See it on your PC in 2 minutes (demo mode, Windows 11)

Demo mode uses sample clips that ship with the app. It needs no Supabase, no keys and no worker, and nothing you click is saved or posted.

1. Install **Node.js 22 LTS** from https://nodejs.org (the Windows Installer, default options).
2. Open **PowerShell** and go to the dashboard folder of the repo, for example:
   ```powershell
   cd C:\Users\<you>\Desktop\clipping\dashboard
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

1. Create a project at https://supabase.com.
2. Run the SQL files in `supabase/migrations/` in order (SQL Editor, paste each file, Run), or `supabase db push` with the Supabase CLI.
3. **Authentication > Sign In / Providers**: keep Email on, turn **off** "Allow new users to sign up".
4. **Authentication > Users > Add user > Send invitation** to your own email. Accept the invite.
5. Make yourself the owner. In the SQL Editor:
   ```sql
   insert into public.owners(user_id)
   select id from auth.users where email = 'YOUR EMAIL';
   ```
6. **Authentication > URL Configuration**: set Site URL to your dashboard address and add `http://localhost:3000/auth/callback` and `https://<your-vercel-domain>/auth/callback` to Redirect URLs.

### 2. Keys on the PC

Copy `.env.example` to `.env.local` in this folder and fill in the two public values from **Project Settings > API**:

```
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon / publishable key>
```

Only the anon (publishable) key goes here. The service-role key belongs to the worker's `.env` and must never be put in the dashboard. `.env.local` is git-ignored.

```powershell
npm run dev
```

Open http://localhost:3000, enter your email, and click the link in the email on the same device.

### 3. Vercel (phone access from anywhere)

1. Import the GitHub repo in Vercel and set **Root Directory** to `dashboard`.
2. Add the same two `NEXT_PUBLIC_SUPABASE_*` variables under Project Settings > Environment Variables.
3. Deploy, then add the Vercel address to Supabase Redirect URLs (step 1.6).
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
