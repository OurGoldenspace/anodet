# Prepares local copy-paste files for the Railway UI. Does not log in or deploy.
# Run from the repo root:  .\scripts\setup-railway.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$out = Join-Path $root "backups"
New-Item -ItemType Directory -Force -Path $out | Out-Null

$pass = -join ((48..57 + 97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
$passFile = Join-Path $out "railway-passphrase.txt"
$apiFile = Join-Path $out "railway-api.env"
$webFile = Join-Path $out "railway-web.env"

Set-Content -Path $passFile -Value $pass -NoNewline
Write-Output "Passphrase written to backups/railway-passphrase.txt (gitignored). Do not commit it."

@"
PORT=8000
RAILWAY_DOCKERFILE_PATH=services/api/Dockerfile
ANODET_DB=/var/lib/anodet/anodet.db
ANODET_DATA=/data/cmapss/train_FD001.txt
SHOP_PASSPHRASE_HINT=0
DEMO_TOOLS=1
SHOP_ID=pilot
SHOP_NAME=Pilot shop
SHOP_LEAD=
SHOP_PASSPHRASE=$pass
CORS_ORIGINS=
XAI_API_KEY=
XAI_MODEL=grok-4
"@ | Set-Content -Path $apiFile

@"
PORT=3000
RAILWAY_DOCKERFILE_PATH=web/Dockerfile
API_PROXY_URL=http://api.railway.internal:8000
"@ | Set-Content -Path $webFile

Write-Output "Raw env files: backups/railway-api.env and backups/railway-web.env"
Write-Output "Paste those into Railway Variables (Raw Editor) after you create services api and web."
Write-Output "After web has a public URL, set CORS_ORIGINS=https://THAT-HOST on api and redeploy api."
Write-Output "Dashboard: https://railway.com/project/aa7f7b70-dc84-4f72-9b03-15262d6deed7?environmentId=a3d53800-56cc-4235-bd90-00ae4908790d"

Start-Process "https://railway.com/project/aa7f7b70-dc84-4f72-9b03-15262d6deed7?environmentId=a3d53800-56cc-4235-bd90-00ae4908790d"
