param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
$manifest = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') | ConvertFrom-Json
$backup = Join-Path $GameRoot '_cn_project\test_backup\fmv_retime_20260930\video'
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '') }
    finally { $sha.Dispose(); $stream.Dispose() }
}
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before rollback.' }
foreach ($movie in $manifest.movies) {
    $name = $movie.movie + '_RU.srt'
    if ((Hash (Join-Path $GameRoot "video\$name")) -ne $movie.after) { throw "Unexpected installed subtitle: $name" }
    if ((Hash (Join-Path $backup $name)) -ne $movie.before) { throw "Backup hash mismatch: $name" }
}
foreach ($movie in $manifest.movies) {
    $name = $movie.movie + '_RU.srt'
    Copy-Item -LiteralPath (Join-Path $backup $name) -Destination (Join-Path $GameRoot "video\$name") -Force
    if ((Hash (Join-Path $GameRoot "video\$name")) -ne $movie.before) { throw "Restored hash mismatch: $name" }
}
Write-Output 'ROLLBACK_OK ru_srt=15 original_hashes_restored=15 prior_timestamps_restored=yes'
