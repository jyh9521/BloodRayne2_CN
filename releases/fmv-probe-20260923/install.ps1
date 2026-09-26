param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = New-Object System.Security.Cryptography.SHA256Managed
    try { ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '') }
    finally { $algorithm.Dispose(); $stream.Dispose() }
}
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before installing subtitles.' }
$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') | ConvertFrom-Json
foreach ($entry in $manifest.required_files.PSObject.Properties) {
    if ((Hash (Join-Path $GameRoot $entry.Name)) -ne $entry.Value) { throw "Requires matching v12 file: $($entry.Name)" }
}
$payload = Join-Path $PSScriptRoot 'payload\video\A1S01P01_RU.srt'
if ((Hash $payload) -ne $manifest.payload_sha256) { throw 'Subtitle payload hash mismatch.' }
$target = Join-Path $GameRoot 'video\A1S01P01_RU.srt'
if (-not (Test-Path -LiteralPath (Split-Path -Parent $target))) { throw 'Game video directory is missing.' }
$backup = Join-Path $GameRoot '_cn_project\test_backup\fmv_probe_20260923'
$statePath = Join-Path $backup 'state.json'
if (Test-Path -LiteralPath $statePath) { throw 'Active subtitle backup exists. Run ROLLBACK.cmd first.' }
$exists = Test-Path -LiteralPath $target
$oldHash = if ($exists) { Hash $target } else { $null }
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$saved = Join-Path $backup 'A1S01P01_RU.original.srt'
if ($exists) { Copy-Item -LiteralPath $target -Destination $saved -Force }
$state = [ordered]@{ existed=$exists; original_sha256=$oldHash; installed_sha256=$manifest.payload_sha256 }
$state | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath $statePath
try {
    Copy-Item -LiteralPath $payload -Destination $target -Force
    if ((Hash $target) -ne $manifest.payload_sha256) { throw 'Installed subtitle hash mismatch.' }
} catch {
    if ($exists) { Copy-Item -LiteralPath $saved -Destination $target -Force }
    elseif (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target }
    Remove-Item -LiteralPath $statePath
    throw
}
Write-Host 'INSTALL_PASS video/A1S01P01_RU.srt cues=6 original=backed_up game_launch=no'
