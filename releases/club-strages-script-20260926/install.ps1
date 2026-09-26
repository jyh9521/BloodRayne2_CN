param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
$target = Join-Path $GameRoot 'COMMON.POD'
$payload = Join-Path $PSScriptRoot 'payload\COMMON.POD'
$backupDir = Join-Path $GameRoot '_cn_project\test_backup\club_strages_script_20260926'
$oldHash = '1CC9A191D478AE87F97B454FD1D0419CE06A31709F8CB5B9D011D75EF83E3F18'
$newHash = '7E07F40F473DC056D289D6F583EAB4A890FD9CEA72BAB667E23E70CEE70C4EE3'
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '') }
    finally { $sha.Dispose(); $stream.Dispose() }
}
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before installing.' }
if ((Hash $target) -ne $oldHash) { throw 'Unexpected current COMMON.POD hash.' }
if ((Hash $payload) -ne $newHash) { throw 'Payload hash mismatch.' }
if (Test-Path -LiteralPath $backupDir) { throw 'Backup already exists.' }
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item -LiteralPath $target -Destination (Join-Path $backupDir 'COMMON.POD')
Copy-Item -LiteralPath $payload -Destination $target -Force
if ((Hash $target) -ne $newHash) { throw 'Installed hash mismatch.' }
Write-Output 'INSTALL_OK COMMON.POD=club_strages_boxed_display other_game_files=unchanged'
