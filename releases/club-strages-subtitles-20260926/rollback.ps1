param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
$target = Join-Path $GameRoot 'LANGUAGE.POD'
$backup = Join-Path $GameRoot '_cn_project\test_backup\club_strages_subtitles_20260926\LANGUAGE.POD'
$oldHash = '18B5FA66F69AD57327D91C54BFD08F3FD9DC34A7C76E15FF53FDBA22F8D35C97'
$newHash = 'CB0EE5C1D0FD6CC7530C46B6CD34E9DB87F68D7912F54D7BC3515DEE9A7F0085'
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
Write-Output 'ROLLBACK_OK LANGUAGE.POD=restored other_game_files=unchanged'
