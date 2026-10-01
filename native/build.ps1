# nguyenphi37
$ErrorActionPreference = "Stop"
$vc = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build"
$here = $PSScriptRoot

function Build-Arch([string]$arch, [string]$bat, [string]$target) {
    $script = Join-Path $here "build-arch.cmd"
    $vcbat = Join-Path $vc $bat
    $command = "call `"$script`" $arch `"$vcbat`" $target"
    cmd.exe /c $command
    if ($LASTEXITCODE -ne 0) {
        throw "Build $arch failed with exit $LASTEXITCODE"
    }
}

Build-Arch "x64" "vcvars64.bat" "X64"
Build-Arch "x86" "vcvars32.bat" "X86"
Write-Output "BUILD_OK"
