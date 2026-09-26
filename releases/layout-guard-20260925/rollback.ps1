param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
$target = Join-Path $GameRoot 'dinput8.dll'
$backup = Join-Path $GameRoot '_cn_project\test_backup\layout_guard_20260925\dinput8.dll'
$oldHash = 'D3AFA1C30E671625E5BE997230B1E13F9280FB2C18652D1672C2A37AB50C934D'
$newHash = '87871E80FBF63F87FA664DF5FA76C05B4F5DDA98348E2B3C656F0335E72A18C2'
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '') }
    finally { $sha.Dispose(); $stream.Dispose() }
}
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before rollback.' }
if ((Hash $target) -ne $newHash) { throw 'Unexpected current dinput8.dll hash.' }
if ((Hash $backup) -ne $oldHash) { throw 'Backup hash mismatch.' }
Copy-Item -LiteralPath $backup -Destination $target -Force
if ((Hash $target) -ne $oldHash) { throw 'Rollback hash mismatch.' }
Write-Output 'ROLLBACK_OK dinput8.dll=restored video_subtitles=unchanged'
