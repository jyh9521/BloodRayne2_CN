param([string]$GameRoot)
$ErrorActionPreference = 'Stop'
if (-not $GameRoot) { $GameRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot = [IO.Path]::GetFullPath($GameRoot)
$backupDir = Join-Path $GameRoot '_cn_project\test_backup\boxed_dialogue_coverage_20260926'
$expectedOld = @{
    'COMMON.POD' = '7E07F40F473DC056D289D6F583EAB4A890FD9CEA72BAB667E23E70CEE70C4EE3'
    'LANGUAGE.POD' = '18B5FA66F69AD57327D91C54BFD08F3FD9DC34A7C76E15FF53FDBA22F8D35C97'
}
$expectedNew = @{
    'COMMON.POD' = '2E39DECB4A6A823A7F4EF0BB8CAB38A51292ADF04B368283B37D5D45B4569186'
    'LANGUAGE.POD' = 'BC758A173AE411003DF748BC4C4BF6C2E240B27E065D9A70B1DCDF9F51E3CE9C'
}
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '') }
    finally { $sha.Dispose(); $stream.Dispose() }
}
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before installing.' }
if (Test-Path -LiteralPath $backupDir) { throw 'Backup already exists.' }
foreach ($name in @('COMMON.POD', 'LANGUAGE.POD')) {
    if ((Hash (Join-Path $GameRoot $name)) -ne $expectedOld[$name]) { throw "Unexpected current $name hash." }
    if ((Hash (Join-Path $PSScriptRoot "payload\$name")) -ne $expectedNew[$name]) { throw "Payload $name hash mismatch." }
}
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
foreach ($name in @('COMMON.POD', 'LANGUAGE.POD')) {
    Copy-Item -LiteralPath (Join-Path $GameRoot $name) -Destination (Join-Path $backupDir $name)
}
try {
    foreach ($name in @('COMMON.POD', 'LANGUAGE.POD')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot "payload\$name") -Destination (Join-Path $GameRoot $name) -Force
        if ((Hash (Join-Path $GameRoot $name)) -ne $expectedNew[$name]) { throw "Installed $name hash mismatch." }
    }
} catch {
    foreach ($name in @('COMMON.POD', 'LANGUAGE.POD')) {
        Copy-Item -LiteralPath (Join-Path $backupDir $name) -Destination (Join-Path $GameRoot $name) -Force
    }
    throw
}
Write-Output 'INSTALL_OK COMMON.POD=boxed_dialogue_coverage LANGUAGE.POD=caption_rows other_game_files=unchanged'
