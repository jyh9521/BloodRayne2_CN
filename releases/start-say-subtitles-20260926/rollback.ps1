param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
$target = Join-Path $GameRoot 'COMMON.POD'
$backup = Join-Path $GameRoot '_cn_project\test_backup\start_say_subtitles_20260926\COMMON.POD'
$oldHash = '2E39DECB4A6A823A7F4EF0BB8CAB38A51292ADF04B368283B37D5D45B4569186'
$newHash = 'AB7EAEB666B74A8131E146A2E8764366CCD92305A08518E064B06D9FEEDDE844'
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '') }
    finally { $sha.Dispose(); $stream.Dispose() }
}
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before rollback.' }
if ((Hash $target) -ne $newHash) { throw 'Unexpected current COMMON.POD hash.' }
if ((Hash $backup) -ne $oldHash) { throw 'Backup COMMON.POD hash mismatch.' }
Copy-Item -LiteralPath $backup -Destination $target -Force
if ((Hash $target) -ne $oldHash) { throw 'Rollback COMMON.POD hash mismatch.' }
Write-Output 'ROLLBACK_OK COMMON.POD=restored other_game_files=unchanged'
