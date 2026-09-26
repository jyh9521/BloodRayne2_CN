$ErrorActionPreference='Stop'
$project=Split-Path -Parent $PSScriptRoot
$root=Split-Path -Parent $project
$out=Join-Path $project 'releases\fmv-full-20260925\payload'
$build=Join-Path $project 'build\fmv_full_20260925'
$source=Join-Path $project 'proxy\fmv_full\dinput8_cn.cpp'
$def=Join-Path $project 'proxy\dinput8.def'
$dev='C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat'
New-Item -ItemType Directory -Force -Path $build | Out-Null
$cmd='"{0}" -no_logo -arch=x86 -host_arch=x64 && cl /nologo /std:c++17 /O2 /MT /EHsc /LD "{1}" /Fo:"{2}\dinput8_cn.obj" /Fe:"{3}\dinput8.dll" user32.lib gdi32.lib ole32.lib /link /DEF:"{4}"' -f $dev,$source,$build,$out,$def
& $env:ComSpec /d /s /c $cmd
if ($LASTEXITCODE -ne 0) {exit $LASTEXITCODE}
$manifest=Join-Path (Split-Path -Parent $out) 'manifest.json'
$m=Get-Content -Raw -Encoding UTF8 -LiteralPath $manifest | ConvertFrom-Json
$stream=[IO.File]::OpenRead((Join-Path $out 'dinput8.dll'));$hash=New-Object Security.Cryptography.SHA256Managed
try {$digest=([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-','')} finally {$hash.Dispose();$stream.Dispose()}
$m.payload | Add-Member -MemberType NoteProperty -Name 'dinput8.dll' -Value $digest -Force
[IO.File]::WriteAllText($manifest,($m | ConvertTo-Json -Depth 25),[Text.UTF8Encoding]::new($false))
Write-Host "FMV_PROXY_BUILD_PASS $digest"
