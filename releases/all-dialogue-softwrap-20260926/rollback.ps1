param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
$target = Join-Path $GameRoot 'LANGUAGE.POD'
$backup = Join-Path $GameRoot '_cn_project\test_backup\all_dialogue_softwrap_20260926\LANGUAGE.POD'
$oldHash = '913E8B65727E9EB5146F276F5680E12C4083D122694A25692AA24325947BF8A4'
$newHash = '1A068F7BA4430B2BA8607B3D81B44F80BFB44E0A95729FBBF8D48F678F01E9A4'
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '') }
    finally { $sha.Dispose(); $stream.Dispose() }
}
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before rollback.' }
if ((Hash $target) -ne $newHash) { throw 'Unexpected current LANGUAGE.POD hash.' }
if ((Hash $backup) -ne $oldHash) { throw 'Backup hash mismatch.' }
Copy-Item -LiteralPath $backup -Destination $target -Force
if ((Hash $target) -ne $oldHash) { throw 'Rollback hash mismatch.' }
Write-Output 'ROLLBACK_OK LANGUAGE.POD=previous_roof_softwrap dinput8.dll=unchanged'
