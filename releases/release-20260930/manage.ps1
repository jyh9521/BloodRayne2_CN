param([ValidateSet('Install','Rollback')][string]$Mode='Install', [string]$GameRoot)
$ErrorActionPreference='Stop'
function Hash([string]$p) {
 $s=[IO.File]::OpenRead($p); $h=[Security.Cryptography.SHA256]::Create()
 try { ([BitConverter]::ToString($h.ComputeHash($s))).Replace('-','').ToLowerInvariant() }
 finally { $s.Dispose(); $h.Dispose() }
}
if (!$GameRoot) {
 if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'rayne2.exe')) { $GameRoot=$PSScriptRoot }
 else { $GameRoot=Read-Host 'Game folder (Steam > Manage > Browse local files)' }
}
$GameRoot=[IO.Path]::GetFullPath($GameRoot.Trim('"'))
if (Get-Process rayne2 -ErrorAction SilentlyContinue) { throw 'Exit BloodRayne 2 first.' }
$manifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ((Hash (Join-Path $GameRoot 'rayne2.exe')) -ne $manifest.game_sha256) { throw 'Game executable version mismatch. No files changed.' }
$backup=Join-Path $GameRoot '_cn_backup_release_20260930'
$stateFile=Join-Path $backup 'restore.json'
if ($Mode -eq 'Install') {
 if (Test-Path -LiteralPath $backup) { throw 'Backup already exists; rollback before reinstalling.' }
 foreach ($f in $manifest.files) {
  if ((Hash (Join-Path $PSScriptRoot ('payload/'+$f.path))) -ne $f.sha256) { throw ('Package hash mismatch: '+$f.path) }
 }
 $dll=Join-Path $GameRoot 'dinput8.dll'
 $own=($manifest.files | Where-Object path -eq 'dinput8.dll').sha256
 if ((Test-Path -LiteralPath $dll) -and (Hash $dll) -ne $own) { throw 'Another dinput8.dll exists. Back it up and resolve proxy conflict first. No files changed.' }
 $records=@()
 foreach ($f in $manifest.files) {
  $p=Join-Path $GameRoot $f.path
  $exists=Test-Path -LiteralPath $p
  $records+= [pscustomobject]@{path=$f.path; existed=$exists; before=$(if($exists){Hash $p}else{$null}); installed=$f.sha256}
 }
 New-Item -ItemType Directory -Path $backup | Out-Null
 foreach ($f in $records) {
  if ($f.existed) {
   $dest=Join-Path $backup ('original/'+$f.path)
   New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($dest)) -Force | Out-Null
   Copy-Item -LiteralPath (Join-Path $GameRoot $f.path) -Destination $dest
   if ((Hash $dest) -ne $f.before) { throw 'Backup verification failed; installation has not started.' }
  }
 }
 $records | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $stateFile -Encoding UTF8
 try {
  foreach ($f in $manifest.files) {
   $dest=Join-Path $GameRoot $f.path
   New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($dest)) -Force | Out-Null
   Copy-Item -LiteralPath (Join-Path $PSScriptRoot ('payload/'+$f.path)) -Destination $dest -Force
   if ((Hash $dest) -ne $f.sha256) { throw ('Installed hash mismatch: '+$f.path) }
  }
 } catch {
  foreach ($f in $records) {
   $dest=Join-Path $GameRoot $f.path
   if ($f.existed) { Copy-Item -LiteralPath (Join-Path $backup ('original/'+$f.path)) -Destination $dest -Force }
   elseif (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest }
  }
  throw
 }
 Write-Output 'INSTALL_OK files=17 hashes=17 backup=verified game_not_started=yes'
} else {
 $records=Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
 if ($records.Count -ne 17) { throw 'Invalid restore manifest.' }
 foreach ($f in $records) {
  $full=[IO.Path]::GetFullPath((Join-Path $GameRoot $f.path))
  if (!$full.StartsWith($GameRoot.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid restore path.' }
  if ($f.path -notin @($manifest.files.path)) { throw 'Unexpected restore entry.' }
  if ((Hash $full) -ne $f.installed) { throw ('Installed file changed; rollback stopped: '+$f.path) }
  if ($f.existed -and (Hash (Join-Path $backup ('original/'+$f.path))) -ne $f.before) { throw 'Original backup hash mismatch.' }
 }
 foreach ($f in $records) {
  $dest=Join-Path $GameRoot $f.path
  if ($f.existed) {
   Copy-Item -LiteralPath (Join-Path $backup ('original/'+$f.path)) -Destination $dest -Force
   if ((Hash $dest) -ne $f.before) { throw 'Restored hash mismatch.' }
  } else { Remove-Item -LiteralPath $dest }
 }
 Write-Output 'ROLLBACK_OK files=17 original_hashes_and_absence=restored backup_retained=yes'
}
