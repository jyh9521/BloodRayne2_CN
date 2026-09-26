param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
$target = Join-Path $GameRoot 'LANGUAGE.POD'
$payload = Join-Path $PSScriptRoot 'payload\LANGUAGE.POD'
$backup = Join-Path $GameRoot '_cn_project\test_backup\all_dialogue_softwrap_20260926'
$oldHash = '913E8B65727E9EB5146F276F5680E12C4083D122694A25692AA24325947BF8A4'
$newHash = '1A068F7BA4430B2BA8607B3D81B44F80BFB44E0A95729FBBF8D48F678F01E9A4'
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
Write-Output 'INSTALL_OK stage_dialogue_softwrap=all changed_entries=36 other_entries=unchanged'
