# Runs INSIDE Windows Sandbox only. Renders the 5 allowed stings with bg=none to ProRes 4444.
$ErrorActionPreference = "Stop"
$env:PATH = "C:\node;C:\ffmpeg;$env:PATH"
$env:HYPERFRAMES_NO_TELEMETRY = "1"; $env:DO_NOT_TRACK = "1"   # hyperframes sends PostHog usage otherwise
$Hf = "hyperframes@0.8.162"                                    # pinned by every Shorts component
$Stings = @(
  @{ name = "wasted";         dir = "shorts\09-wasted-stamp";   variant = "0" },
  @{ name = "busted";         dir = "shorts\09-wasted-stamp";   variant = "1" },
  @{ name = "mission_passed"; dir = "shorts\10-mission-passed"; variant = "0" },
  @{ name = "mission_failed"; dir = "shorts\10-mission-passed"; variant = "1" },
  @{ name = "wanted_level";   dir = "shorts\08-wanted-level";   variant = "0" }
)
$Work = "C:\work"
Copy-Item -Recurse C:\gta $Work          # the mapped repo is read-only; setup.sh would write into it
foreach ($s in $Stings) {
  $p = Join-Path $Work $s.dir
  # same as setup.sh: shared fonts + Shorts kit into assets\, empty footage folders (bg=none hides them)
  foreach ($d in "fonts","kit","shots","plates","clips") { New-Item -ItemType Directory -Force "$p\assets\$d" | Out-Null }
  Copy-Item -Recurse -Force "$Work\shared\fonts\*" "$p\assets\fonts\"
  Copy-Item -Recurse -Force "$Work\shared\kit-shorts\*" "$p\assets\kit\"
  $vars = '{\"bg\":\"none\",\"variant\":\"' + $s.variant + '\"}'
  $out = "C:\out\$($s.name)-v1.mov"
  Push-Location $p
  npx --yes $Hf render . -o $out --format mov --fps 30 --variables $vars
  Pop-Location
  if (-not (Test-Path $out)) { throw "no output for $($s.name)" }
  Write-Host "baked $out"
}
Write-Host "All 5 stings baked. Close this Sandbox window (nothing in it is kept)."
