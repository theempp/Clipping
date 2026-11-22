# Keeps `claude --channels discord` alive. Single instance, restarts on exit/crash.
$ErrorActionPreference = 'Continue'
$dir = $PSScriptRoot
$proj = Split-Path (Split-Path $dir)
$log = Join-Path $dir 'bot.log'

$created = $false
$mutex = New-Object System.Threading.Mutex($true, 'Global\ClipDiscordBot', [ref]$created)
if (-not $created) { exit 0 }

$prompt = Get-Content (Join-Path $dir 'prompt.md') -Raw
Set-Location $proj
# Call the real exe: the claude.cmd shim truncates multi-line args at the first newline.
$exe = Join-Path $env:APPDATA 'npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe'
if (-not (Test-Path $exe)) { $exe = 'claude.exe' }
$fast = 0
while ($true) {
  $t0 = Get-Date
  "[{0}] starting claude" -f $t0.ToString('s') | Add-Content $log
  & $exe --channels plugin:discord@claude-plugins-official `
    --settings (Join-Path $dir 'settings.json') `
    --append-system-prompt $prompt
  $secs = ((Get-Date) - $t0).TotalSeconds
  "[{0}] claude exited code {1} after {2:n0}s" -f (Get-Date).ToString('s'), $LASTEXITCODE, $secs | Add-Content $log
  if ($secs -lt 60) { $fast++ } else { $fast = 0 }
  Start-Sleep -Seconds ([Math]::Min(300, 10 * [Math]::Pow(2, [Math]::Min($fast, 5))))
}
