param(
  [string]$Dest = "backups",
  [int]$Keep = 14
)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
& "$root\services\api\.venv\Scripts\python.exe" "$root\scripts\backup-shop-memory.py" --dest $Dest --keep $Keep
if ($LASTEXITCODE -ne 0) {
  python "$root\scripts\backup-shop-memory.py" --dest $Dest --keep $Keep
}
