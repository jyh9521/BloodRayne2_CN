param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
$manifest = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') | ConvertFrom-Json
$oldDll = $manifest.before.'dinput8.dll'
$oldPod = $manifest.before.'LANGUAGE.POD'
$newDll = 'D525CB5521FADC0373641E6CF7EDBF988E5FB178EC65B61670CD85A5139A09DC'
$newPod = $manifest.language_after
$backup = Join-Path $GameRoot '_cn_project\test_backup\engine_voice_subtitles_20260927'
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '') }
    finally { $sha.Dispose(); $stream.Dispose() }
}
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before installing.' }
foreach ($name in @('dinput8.dll', 'LANGUAGE.POD')) {
    $target = Join-Path $GameRoot $name
    $payload = Join-Path $PSScriptRoot "payload\$name"
    $wantOld = if ($name -eq 'dinput8.dll') { $oldDll } else { $oldPod }
    $wantNew = if ($name -eq 'dinput8.dll') { $newDll } else { $newPod }
    if ((Hash $target) -ne $wantOld) { throw "Unexpected current $name hash." }
    if ((Hash $payload) -ne $wantNew) { throw "Unexpected payload $name hash." }
}
if (Test-Path -LiteralPath $backup) { throw 'Backup already exists.' }
New-Item -ItemType Directory -Path $backup -Force | Out-Null
foreach ($name in @('dinput8.dll', 'LANGUAGE.POD')) {
    Copy-Item -LiteralPath (Join-Path $GameRoot $name) -Destination (Join-Path $backup $name)
}
try {
    foreach ($name in @('dinput8.dll', 'LANGUAGE.POD')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot "payload\$name") -Destination (Join-Path $GameRoot $name) -Force
        $wantNew = if ($name -eq 'dinput8.dll') { $newDll } else { $newPod }
        if ((Hash (Join-Path $GameRoot $name)) -ne $wantNew) { throw "Install verify failed: $name" }
    }
} catch {
    foreach ($name in @('dinput8.dll', 'LANGUAGE.POD')) {
        Copy-Item -LiteralPath (Join-Path $backup $name) -Destination (Join-Path $GameRoot $name) -Force
    }
    throw
}
Write-Output 'INSTALL_OK dinput8.dll=voice_caption_hook LANGUAGE.POD=font_glyphs COMMON.POD=unchanged W32ENSND.POD=unchanged'
