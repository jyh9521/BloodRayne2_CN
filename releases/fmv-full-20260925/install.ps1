param([string]$GameRoot)
$ErrorActionPreference='Stop'
if (-not $GameRoot) { $GameRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..')) }
$GameRoot=[IO.Path]::GetFullPath($GameRoot)
function Hash([string]$Path) {
    $s=[IO.File]::OpenRead($Path);$a=New-Object Security.Cryptography.SHA256Managed
    try { ([BitConverter]::ToString($a.ComputeHash($s))).Replace('-','') } finally { $a.Dispose();$s.Dispose() }
}
function Target([string]$Name) {
    if ($Name -notmatch '^(LANGUAGE\.POD|dinput8\.dll|video/[A-Z0-9]+_RU\.srt)$') { throw 'Unexpected deployment path.' }
    $p=[IO.Path]::GetFullPath((Join-Path $GameRoot $Name))
    if (-not $p.StartsWith($GameRoot.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Target escaped game directory.' }
    return $p
}
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Close the game before installing.' }
$m=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') | ConvertFrom-Json
foreach ($p in $m.required_before.PSObject.Properties) {
    if ((Hash (Join-Path $GameRoot $p.Name)) -ne $p.Value) { throw "Requires the matching v12 file: $($p.Name)" }
}
$backup=Join-Path $GameRoot '_cn_project\test_backup\fmv_full_20260925'
$statePath=Join-Path $backup 'state.json'
if (Test-Path -LiteralPath $statePath) { throw 'An active full-FMV backup exists. Roll it back first.' }
$entries=@();$i=0
foreach ($p in $m.payload.PSObject.Properties) {
    $dst=Target $p.Name
    $src=Join-Path (Join-Path $PSScriptRoot 'payload') $p.Name
    if ((Hash $src) -ne $p.Value) { throw "Package hash mismatch: $($p.Name)" }
    if (-not (Test-Path -LiteralPath (Split-Path -Parent $dst))) { throw 'Target directory missing.' }
    $exists=Test-Path -LiteralPath $dst
    $old=if($exists){Hash $dst}else{$null}
    $entries+= [pscustomobject]@{name=$p.Name;existed=$exists;original_sha256=$old;installed_sha256=$p.Value;backup_file=("{0:D2}.bin" -f $i)}
    $i++
}
if ($entries.Count -ne 17) { throw 'Expected exactly two runtime files and fifteen subtitle files.' }
New-Item -ItemType Directory -Force -Path $backup | Out-Null
foreach ($e in $entries) {
    if ($e.existed) {
        $saved=Join-Path $backup $e.backup_file
        Copy-Item -LiteralPath (Target $e.name) -Destination $saved -Force
        if ((Hash $saved) -ne $e.original_sha256) { throw 'Backup verification failed before installation.' }
    }
}
[ordered]@{build_id=$m.build_id;entries=$entries} | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath $statePath
try {
    foreach ($e in $entries) {
        Copy-Item -LiteralPath (Join-Path (Join-Path $PSScriptRoot 'payload') $e.name) -Destination (Target $e.name) -Force
        if ((Hash (Target $e.name)) -ne $e.installed_sha256) { throw "Installed hash mismatch: $($e.name)" }
    }
} catch {
    foreach ($e in $entries) {
        $dst=Target $e.name
        if ($e.existed) { Copy-Item -LiteralPath (Join-Path $backup $e.backup_file) -Destination $dst -Force }
        elseif (Test-Path -LiteralPath $dst) { Remove-Item -LiteralPath $dst }
    }
    Remove-Item -LiteralPath $statePath
    throw
}
Write-Host 'INSTALL_PASS movies=15 cues=222 backed_up=yes W32ART_W32ENSND_BIK=untouched game_launch=no'
