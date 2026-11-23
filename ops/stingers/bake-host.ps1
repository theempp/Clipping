# Host side of the D115 stinger bake. Runs nothing from the repo on the host: it clones, checks the
# audited commit, and starts Windows Sandbox with the repo read-only and one writable output folder.
$ErrorActionPreference = "Stop"
$Sha   = "81181fda29c98b53a0d14659d8d1dafd62d84060"
$Repo  = "C:\clip-work\quarantine\gta-components"
$Out   = "C:\clip-work\stingers"
$Here  = $PSScriptRoot

if (-not (Test-Path "$env:windir\System32\WindowsSandbox.exe")) { throw "Windows Sandbox is off. See README step 1." }
if (-not (Test-Path $Repo)) { git clone --quiet https://github.com/echris6/gta-components.git $Repo }
git -C $Repo fetch --quiet origin
git -C $Repo -c advice.detachedHead=false checkout --quiet $Sha
if ((git -C $Repo rev-parse HEAD) -ne $Sha) { throw "gta-components is not at the audited commit" }
New-Item -ItemType Directory -Force $Out | Out-Null

$node   = Split-Path (Get-Command node.exe).Source
$ffmpeg = Split-Path (Get-Command ffmpeg.exe).Source

@"
<Configuration>
  <Networking>Enable</Networking>
  <ClipboardRedirection>Disable</ClipboardRedirection>
  <PrinterRedirection>Disable</PrinterRedirection>
  <MappedFolders>
    <MappedFolder><HostFolder>$Repo</HostFolder><SandboxFolder>C:\gta</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>$Here</HostFolder><SandboxFolder>C:\bake</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>$node</HostFolder><SandboxFolder>C:\node</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>$ffmpeg</HostFolder><SandboxFolder>C:\ffmpeg</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>$Out</HostFolder><SandboxFolder>C:\out</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder>
  </MappedFolders>
  <LogonCommand><Command>powershell -ExecutionPolicy Bypass -NoExit -File C:\bake\bake-inside.ps1</Command></LogonCommand>
</Configuration>
"@ | Set-Content -Encoding UTF8 "$Here\bake.wsb"
Start-Process "$Here\bake.wsb"
Write-Host "Sandbox started. Files land in $Out"
