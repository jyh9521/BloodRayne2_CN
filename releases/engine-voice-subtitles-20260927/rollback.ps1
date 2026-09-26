param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
$manifest = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') | ConvertFrom-Json
$backup = Join-Path $GameRoot '_cn_project\test_backup\engine_voice_subtitles_20260927'
$newDll = 'D525CB5521FADC0373641E6CF7EDBF988E5FB178EC65B61670CD85A5139A09DC'
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '') }
    finally { $sha.Dispose(); $stream.Dispose() }
}
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before rollback.' }
foreach ($name in @('dinput8.dll', 'LANGUAGE.POD')) {
    $wantNew = if ($name -eq 'dinput8.dll') { $newDll } else { $manifest.language_after }
    $wantOld = $manifest.before.$name
    if ((Hash (Join-Path $GameRoot $name)) -ne $wantNew) { throw "Unexpected installed $name hash." }
    if ((Hash (Join-Path $backup $name)) -ne $wantOld) { throw "Unexpected backup $name hash." }
}
foreach ($name in @('dinput8.dll', 'LANGUAGE.POD')) {
    Copy-Item -LiteralPath (Join-Path $backup $name) -Destination (Join-Path $GameRoot $name) -Force
    if ((Hash (Join-Path $GameRoot $name)) -ne $manifest.before.$name) { throw "Rollback verify failed: $name" }
}
Write-Output 'ROLLBACK_OK dinput8.dll=restored LANGUAGE.POD=restored COMMON.POD=unchanged W32ENSND.POD=unchanged'
