param([string]$GameRoot)
$ErrorActionPreference='Stop'
if (-not $GameRoot) { $GameRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot=[IO.Path]::GetFullPath($GameRoot)
function Hash([string]$Path) {
    $s=[IO.File]::OpenRead($Path);$a=New-Object Security.Cryptography.SHA256Managed
    try { ([BitConverter]::ToString($a.ComputeHash($s))).Replace('-','') } finally { $a.Dispose();$s.Dispose() }
}
function Target([string]$Name) {
    if ($Name -notmatch '^(LANGUAGE\.POD|dinput8\.dll|video/[A-Z0-9]+_RU\.srt)$') { throw 'Unexpected rollback path.' }
    $p=[IO.Path]::GetFullPath((Join-Path $GameRoot $Name))
    if (-not $p.StartsWith($GameRoot.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Target escaped game directory.' }
    return $p
}
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before rollback.' }
$backup=Join-Path $GameRoot '_cn_project\test_backup\fmv_full_20260925'
$statePath=Join-Path $backup 'state.json'
if (-not (Test-Path -LiteralPath $statePath)) { throw 'No active full-FMV backup.' }
$state=Get-Content -Raw -Encoding UTF8 -LiteralPath $statePath | ConvertFrom-Json
if ($state.build_id -ne 'fmv-full-v13-20260925' -or $state.entries.Count -ne 17) { throw 'Unexpected backup manifest.' }
# Validate every backup and current target before the first restore write.
foreach ($e in $state.entries) {
    $dst=Target $e.name
    if ($e.backup_file -notmatch '^\d{2}\.bin$') { throw 'Unexpected backup filename.' }
    if ($e.existed -and (Hash (Join-Path $backup $e.backup_file)) -ne $e.original_sha256) { throw 'Original backup hash mismatch.' }
    if (Test-Path -LiteralPath $dst) {
        $now=Hash $dst
        if ($now -ne $e.installed_sha256 -and $now -ne $e.original_sha256) { throw "File changed since installation; preserve your edits first: $($e.name)" }
    }
}
foreach ($e in $state.entries) {
    $dst=Target $e.name
    if ($e.existed) {
        Copy-Item -LiteralPath (Join-Path $backup $e.backup_file) -Destination $dst -Force
        if ((Hash $dst) -ne $e.original_sha256) { throw 'Restored hash mismatch.' }
    } elseif (Test-Path -LiteralPath $dst) { Remove-Item -LiteralPath $dst }
}
Remove-Item -LiteralPath $statePath
Write-Host 'ROLLBACK_PASS prior LANGUAGE_DLL_SRT hashes_and_absence=restored mods=untouched'
