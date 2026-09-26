param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
$target = Join-Path $GameRoot 'LANGUAGE.POD'
$backup = Join-Path $GameRoot '_cn_project\test_backup\a1_part4_softwrap_20260925\LANGUAGE.POD'
$oldHash = '3B9A1D0F9BAA338FFE739B27B05AA6FB87D07E17DCDEE15A0CEE55AF1C0319BC'
$newHash = 'D703A8BA1A6C48C180B6F58F015A9D25678D608DF9326F7FEF332357078F6BA4'
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '') }
    finally { $sha.Dispose(); $stream.Dispose() }
}
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before rollback.' }
if ((Hash $target) -ne $newHash) { throw 'Unexpected current LANGUAGE.POD hash.' }
if ((Hash $backup) -ne $oldHash) { throw 'Backup hash mismatch.' }
Copy-Item -LiteralPath $backup -Destination $target -Force
if ((Hash $target) -ne $oldHash) { throw 'Rollback hash mismatch.' }
Write-Output 'ROLLBACK_OK LANGUAGE.POD=part4_original dinput8.dll=unchanged'
