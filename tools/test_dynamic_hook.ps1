param([switch]$Baseline)
$ErrorActionPreference='Stop'
$project=Split-Path -Parent $PSScriptRoot
$out=Join-Path $project 'build\release_20260923'
$source=Join-Path $PSScriptRoot 'test_dynamic_hook.cpp'
$dev='C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat'
$variant=if($Baseline){'baseline'}else{'modified'}
$define=if($Baseline){'/DCN_TEST_SOURCE=\"../build/release_20260923/original/dinput8_cn.cpp\"'}else{''}
$cmd='"{0}" -no_logo -arch=x86 -host_arch=x64 && cl /nologo /std:c++17 /O2 /MT /EHsc {1} "{2}" /Fo:"{3}\hook_{4}.obj" /Fe:"{3}\hook_{4}.exe" user32.lib gdi32.lib ole32.lib' -f $dev,$define,$source,$out,$variant
& $env:ComSpec /d /s /c $cmd
if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}
& (Join-Path $out "hook_$variant.exe")
exit $LASTEXITCODE
