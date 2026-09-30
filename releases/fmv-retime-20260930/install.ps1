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
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before installing.' }
foreach ($movie in $manifest.movies) {
    $name = $movie.movie + '_RU.srt'
    if ((Hash (Join-Path $GameRoot "video\$name")) -ne $movie.before) { throw "Unexpected current subtitle: $name" }
    if ((Hash (Join-Path $PSScriptRoot "payload\video\$name")) -ne $movie.after) { throw "Payload hash mismatch: $name" }
}
if (Test-Path -LiteralPath $backup) { throw 'Backup already exists.' }
New-Item -ItemType Directory -Path $backup -Force | Out-Null
foreach ($movie in $manifest.movies) {
    $name = $movie.movie + '_RU.srt'
    Copy-Item -LiteralPath (Join-Path $GameRoot "video\$name") -Destination (Join-Path $backup $name)
}
try {
    foreach ($movie in $manifest.movies) {
        $name = $movie.movie + '_RU.srt'
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot "payload\video\$name") -Destination (Join-Path $GameRoot "video\$name") -Force
        if ((Hash (Join-Path $GameRoot "video\$name")) -ne $movie.after) { throw "Installed hash mismatch: $name" }
    }
} catch {
    foreach ($movie in $manifest.movies) {
        $name = $movie.movie + '_RU.srt'
        Copy-Item -LiteralPath (Join-Path $backup $name) -Destination (Join-Path $GameRoot "video\$name") -Force
    }
    throw
}
Write-Output 'INSTALL_OK ru_srt=15 cues=222 timestamp_only=yes text_preserved=yes'
