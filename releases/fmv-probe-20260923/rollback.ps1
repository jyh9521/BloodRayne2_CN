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
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before restoring subtitles.' }
$backup = Join-Path $GameRoot '_cn_project\test_backup\fmv_probe_20260923'
$statePath = Join-Path $backup 'state.json'
if (-not (Test-Path -LiteralPath $statePath)) { throw 'No active FMV subtitle backup.' }
$state = Get-Content -Raw -Encoding UTF8 -LiteralPath $statePath | ConvertFrom-Json
$target = Join-Path $GameRoot 'video\A1S01P01_RU.srt'
if ((Test-Path -LiteralPath $target) -and (Hash $target) -ne $state.installed_sha256) {
    throw 'Subtitle changed after installation. Preserve your edits before rollback.'
}
if ($state.existed) {
    $saved = Join-Path $backup 'A1S01P01_RU.original.srt'
    if ((Hash $saved) -ne $state.original_sha256) { throw 'Original subtitle backup hash mismatch.' }
    Copy-Item -LiteralPath $saved -Destination $target -Force
    if ((Hash $target) -ne $state.original_sha256) { throw 'Restored subtitle hash mismatch.' }
} elseif (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target }
Remove-Item -LiteralPath $statePath
Write-Host 'ROLLBACK_PASS original subtitle state restored; all other game files untouched'
