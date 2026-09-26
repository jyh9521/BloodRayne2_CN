param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
$target = Join-Path $GameRoot 'COMMON.POD'
$payload = Join-Path $PSScriptRoot 'payload\COMMON.POD'
$backupDir = Join-Path $GameRoot '_cn_project\test_backup\start_say_subtitles_20260926'
$oldHash = '2E39DECB4A6A823A7F4EF0BB8CAB38A51292ADF04B368283B37D5D45B4569186'
$newHash = 'AB7EAEB666B74A8131E146A2E8764366CCD92305A08518E064B06D9FEEDDE844'
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '') }
    finally { $sha.Dispose(); $stream.Dispose() }
}
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before installing.' }
if ((Hash $target) -ne $oldHash) { throw 'Unexpected current COMMON.POD hash.' }
if ((Hash $payload) -ne $newHash) { throw 'Payload COMMON.POD hash mismatch.' }
if (Test-Path -LiteralPath $backupDir) { throw 'Backup already exists.' }
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item -LiteralPath $target -Destination (Join-Path $backupDir 'COMMON.POD')
try {
    Copy-Item -LiteralPath $payload -Destination $target -Force
    if ((Hash $target) -ne $newHash) { throw 'Installed COMMON.POD hash mismatch.' }
} catch {
    Copy-Item -LiteralPath (Join-Path $backupDir 'COMMON.POD') -Destination $target -Force
    throw
}
Write-Output 'INSTALL_OK COMMON.POD=start_say_boxed_subtitles other_game_files=unchanged'
