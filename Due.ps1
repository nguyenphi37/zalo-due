$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$dll = Join-Path $PSScriptRoot "native\build\x86\DueHook.dll"
$sources = @(
  "native\DueHook.cpp",
  "native\DueLaunch.cpp",
  "native\DueProbe.cpp"
)
$needsBuild = -not (Test-Path $dll)
if (-not $needsBuild) {
  $built = (Get-Item $dll).LastWriteTime
  foreach ($source in $sources) {
    if ((Get-Item (Join-Path $PSScriptRoot $source)).LastWriteTime -gt $built) {
      $needsBuild = $true
    }
  }
}
if ($needsBuild) {
  & (Join-Path $PSScriptRoot "native\build.cmd")
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
$pythonw = Join-Path $PSScriptRoot ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
  python -m venv (Join-Path $PSScriptRoot ".venv")
  & (Join-Path $PSScriptRoot ".venv\Scripts\python.exe") -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
}
Start-Process -FilePath $pythonw -ArgumentList @("`"$PSScriptRoot\app\main.py`"") -WorkingDirectory $PSScriptRoot
