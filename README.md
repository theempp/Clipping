# Clipp

Zo's private clipping tool: a PC worker detects and renders clips from roster streams, a Next.js dashboard reviews them, and nothing publishes without approval. This folder is also the Obsidian vault; start at [clipping.md](clipping.md) and the [Decision Log](Decision%20Log.md).

- `worker/` Python clip worker (`clipworker`), tests in `worker/tests`
- `dashboard/` Next.js review dashboard
- `supabase/` migrations and SQL tests
- `ops/discord-bot/` Discord bot runner
- `docs/` project overview PDF (`node docs/build.js` rebuilds it)
- `references/pinterest/` design references (only source of visual values)
- `logo-concepts/zwoclippe-final/` final logo files

## Run on the PC
- Use `main` in `C:\clip-work\Clipping` (the Desktop path's `!` breaks Webpack).
- Dashboard: double-click `Start Dashboard.cmd`, open http://localhost:3000 after Ready, log in from Chrome on the PC.
- Secrets live only in `worker/.env` and `dashboard/.env.local` (gitignored).
