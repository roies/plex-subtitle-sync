param(
    [string]$PlexToken = "",
    [string]$PlexUrl = "http://localhost:32400",
    [string]$TargetLang = "he",
    [string]$SourceLang = "en",
    [int]$PollInterval = 15
)

$ErrorActionPreference = 'Stop'

function Write-Info([string]$Message) {
    Write-Host "[+] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "[!] $Message" -ForegroundColor Yellow
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host 'Python 3 was not found. Please install it from https://www.python.org/downloads/windows/' -ForegroundColor Red
    exit 1
}

$PythonExe = (Get-Command python).Source
Write-Info "Using Python: $PythonExe"

if (-not $PlexToken) {
    $PlexToken = Read-Host 'Enter your Plex token (leave blank for local no-auth)'
}
if (-not $PlexUrl) {
    $PlexUrl = Read-Host 'Plex URL [http://localhost:32400]'
}
if (-not $PlexUrl) { $PlexUrl = 'http://localhost:32400' }

Write-Info 'Installing/updating required packages...'
& $PythonExe -m pip install --upgrade "git+https://github.com/roies/plex-auto-subs" ffsubsync argostranslate | Out-Null

Write-Info 'Starting plex-auto-subs...'
$env:PLEX_URL = $PlexUrl
$env:PLEX_TOKEN = $PlexToken
$env:TARGET_LANG = $TargetLang
$env:SOURCE_LANG = $SourceLang
$env:POLL_INTERVAL = $PollInterval

& $PythonExe -m run_daemon
