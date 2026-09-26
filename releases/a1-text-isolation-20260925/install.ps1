param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
$target = Join-Path $GameRoot 'LANGUAGE.POD'
$payload = Join-Path $PSScriptRoot 'payload\LANGUAGE.POD'
$backup = Join-Path $GameRoot '_cn_project\test_backup\a1_text_isolation_20260925'
$oldHash = '3D362A472C6BECF2F2F332055831BDFA1139870FD6D4A9190DA5B1274B46BCB5'
$newHash = '92199661B9E3E07C98A216269B2BFA629433073268CE9620539156B7EF26C9A9'
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
Write-Output 'INSTALL_OK a1_ru_text=original other_entries=unchanged'
