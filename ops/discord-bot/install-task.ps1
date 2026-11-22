# Registers the login task (current user, no admin needed). Re-run to update.
$script = Join-Path $PSScriptRoot 'run-bot.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -RestartCount 99 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'ClipDiscordBot' -Action $action -Trigger $trigger -Settings $settings `
  -Description 'Keeps claude --channels discord running (clip ops bot)' -Force | Out-Null
Get-ScheduledTask ClipDiscordBot | Select TaskName, State
