param()

$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$source = Join-Path $project 'proxy\dinput8_cn.cpp'
$definition = Join-Path $project 'proxy\dinput8.def'
$output = Join-Path $project 'build\proxy'
$logs = Join-Path $project 'logs'
$vsDevCmd = 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat'

if (-not (Test-Path -LiteralPath $vsDevCmd)) {
    throw "Visual Studio environment script not found: $vsDevCmd"
}

New-Item -ItemType Directory -Force -Path $output, $logs | Out-Null
$compilerCommand = @(
    'cl.exe'
    '/nologo'
    '/std:c++17'
    '/O2'
    '/MT'
    '/EHsc'
    '/LD'
    ('/Fo:"{0}\\"' -f $output)
    ('/Fe:"{0}\dinput8.dll"' -f $output)
    ('"{0}"' -f $source)
    'user32.lib'
    'gdi32.lib'
    'ole32.lib'
    '/link'
    ('/DEF:"{0}"' -f $definition)
) -join ' '

$command = '"{0}" -no_logo -arch=x86 -host_arch=x64 && {1}' -f $vsDevCmd, $compilerCommand
& $env:ComSpec /d /s /c $command
if ($LASTEXITCODE -ne 0) {
    throw "Proxy build failed with exit code $LASTEXITCODE"
}

$dll = Join-Path $output 'dinput8.dll'
if (-not (Test-Path -LiteralPath $dll)) {
    throw "Compiler did not produce: $dll"
}
Get-FileHash -Algorithm SHA256 -LiteralPath $dll
