@echo off
setlocal DisableDelayedExpansion
rem Use the maintained checkout, avoiding the ! in the Windows user folder.
cd /d C:\clip-work\Clipping\dashboard
if errorlevel 1 (
  echo Dashboard checkout missing: C:\clip-work\Clipping\dashboard
  pause
  exit /b 1
)
echo Starting the current dashboard at http://localhost:3000
call npm run dev -- --hostname 127.0.0.1 --port 3000
pause
