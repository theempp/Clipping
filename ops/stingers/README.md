# GTA stingers (D115)

Five GTA stings from [echris6/gta-components](https://github.com/echris6/gta-components), baked once to
transparent ProRes 4444 `.mov` files. The worker only overlays these files with ffmpeg; it never runs
HyperFrames, Node or a browser.

Audited commit: `81181fda29c98b53a0d14659d8d1dafd62d84060` (repo-audit 2026-11-23, pass-with-limits,
see Tools and Repos). Allowed: baking the 5 stings below with `bg=none`, in Windows Sandbox only.
Never bake the repo's zoom components (D112).

| File | Component | Variant | Fits (judge category) |
|---|---|---|---|
| wasted-v1.mov | shorts/09-wasted-stamp | 0 | fail |
| busted-v1.mov | shorts/09-wasted-stamp | 1 | fail, rage |
| mission_passed-v1.mov | shorts/10-mission-passed | 0 | clutch |
| mission_failed-v1.mov | shorts/10-mission-passed | 1 | fail, funny |
| wanted_level-v1.mov | shorts/08-wanted-level | 0 | rage, clutch |

## Bake (zo's PC, about 15 minutes)
1. Windows Sandbox must be on: Start > "Turn Windows features on or off" > tick **Windows Sandbox** > OK > restart.
2. In PowerShell: `cd C:\clip-work\Clipping\ops\stingers; .\bake-host.ps1`
   It clones the repo at the audited commit into `C:\clip-work\quarantine\gta-components`, checks the
   commit, writes `bake.wsb` and opens the Sandbox. The Sandbox renders the 5 files into
   `C:\clip-work\stingers\` and closes its window when done. No credentials go into the Sandbox.
3. Turn it on in the worker config: `[extra] stinger_dir = "C:/clip-work/stingers"`.
4. Look at the files before any clip uses them (style sign-off, D022).

The stinger is one optional tool in the D114 toolbox (`gta_stinger`): GTA 6 streams only, at most one per
clip, laid on the peak, weighted and learned like every other tool. Wasted, Busted and Mission failed drain
the clip to black-and-white under the sting.
