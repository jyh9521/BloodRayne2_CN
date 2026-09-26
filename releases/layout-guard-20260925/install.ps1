param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
$target = Join-Path $GameRoot 'dinput8.dll'
$payload = Join-Path $PSScriptRoot 'payload\dinput8.dll'
$backup = Join-Path $GameRoot '_cn_project\test_backup\layout_guard_20260925'
$oldHash = 'D3AFA1C30E671625E5BE997230B1E13F9280FB2C18652D1672C2A37AB50C934D'
$newHash = '87871E80FBF63F87FA664DF5FA76C05B4F5DDA98348E2B3C656F0335E72A18C2'
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '') }
    finally { $sha.Dispose(); $stream.Dispose() }
}
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before installing.' }
if ((Hash $target) -ne $oldHash) { throw 'Unexpected current dinput8.dll hash.' }
if ((Hash $payload) -ne $newHash) { throw 'Payload hash mismatch.' }
if (Test-Path -LiteralPath $backup) { throw 'Backup already exists.' }
New-Item -ItemType Directory -Force -Path $backup | Out-Null
Copy-Item -LiteralPath $target -Destination (Join-Path $backup 'dinput8.dll')
Copy-Item -LiteralPath $payload -Destination $target -Force
if ((Hash $target) -ne $newHash) { throw 'Installed hash mismatch.' }
Write-Output 'INSTALL_OK layout_scan=bounded other_files=unchanged'
