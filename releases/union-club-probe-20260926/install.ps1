param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
$target = Join-Path $GameRoot 'dinput8.dll'
$payload = Join-Path $PSScriptRoot 'payload\dinput8.dll'
$backupDir = Join-Path $GameRoot '_cn_project\test_backup\union_club_probe_20260926'
$oldHash = '74BEEA7D2C91F71E142907EA4B26DB104B344D0F0EA6E7A325BE356BB17EF238'
$newHash = '9E2CE9D0127EEE76E4D6C2C5097FF975B5B8F2F9CF2D0FE489AF354C5782B1A9'
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '') }
    finally { $sha.Dispose(); $stream.Dispose() }
}
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before installing.' }
if ((Hash $target) -ne $oldHash) { throw 'Unexpected current dinput8.dll hash.' }
if ((Hash $payload) -ne $newHash) { throw 'Payload hash mismatch.' }
if (Test-Path -LiteralPath $backupDir) { throw 'Backup already exists.' }
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item -LiteralPath $target -Destination (Join-Path $backupDir 'dinput8.dll')
Copy-Item -LiteralPath $payload -Destination $target -Force
if ((Hash $target) -ne $newHash) { throw 'Installed hash mismatch.' }
Write-Output 'INSTALL_OK union_club_probe=enabled language_and_audio=unchanged'
