param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
$target = Join-Path $GameRoot 'LANGUAGE.POD'
$payload = Join-Path $PSScriptRoot 'payload\LANGUAGE.POD'
$backup = Join-Path $GameRoot '_cn_project\test_backup\a1_part4_softwrap_20260925'
$oldHash = '3B9A1D0F9BAA338FFE739B27B05AA6FB87D07E17DCDEE15A0CEE55AF1C0319BC'
$newHash = 'D703A8BA1A6C48C180B6F58F015A9D25678D608DF9326F7FEF332357078F6BA4'
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '') }
    finally { $sha.Dispose(); $stream.Dispose() }
}
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before installing.' }
if ((Hash $target) -ne $oldHash) { throw 'Unexpected current LANGUAGE.POD hash.' }
if ((Hash $payload) -ne $newHash) { throw 'Payload hash mismatch.' }
if (Test-Path -LiteralPath $backup) { throw 'Backup already exists.' }
New-Item -ItemType Directory -Force -Path $backup | Out-Null
Copy-Item -LiteralPath $target -Destination (Join-Path $backup 'LANGUAGE.POD')
Copy-Item -LiteralPath $payload -Destination $target -Force
if ((Hash $target) -ne $newHash) { throw 'Installed hash mismatch.' }
Write-Output 'INSTALL_OK part4=chinese_softwrap other_entries=unchanged'
