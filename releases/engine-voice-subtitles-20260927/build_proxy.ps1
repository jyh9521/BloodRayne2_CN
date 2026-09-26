param()
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$source = Join-Path $here 'source\dinput8_cn.cpp'
$definition = Join-Path $here 'source\dinput8.def'
$output = Join-Path $here 'payload'
$vc = 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat'
if (-not (Test-Path -LiteralPath $vc)) { throw "Compiler setup missing: $vc" }
$command = @(
    'cl.exe /nologo /std:c++17 /O2 /MT /EHsc /LD',
    ('/Fo:"{0}\\"' -f $output),
    ('/Fe:"{0}\dinput8.dll"' -f $output),
    ('"{0}"' -f $source),
    'user32.lib gdi32.lib ole32.lib',
    '/link',
    ('/DEF:"{0}"' -f $definition)
) -join ' '
& $env:ComSpec /d /s /c ('"{0}" -no_logo -arch=x86 -host_arch=x64 && {1}' -f $vc, $command)
if ($LASTEXITCODE -ne 0) { throw "cl.exe failed: $LASTEXITCODE" }
$dll = Join-Path $output 'dinput8.dll'
if (-not (Test-Path -LiteralPath $dll)) { throw "Missing output: $dll" }
Write-Output ('PROXY_BUILD_OK SHA256=' + (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash)
