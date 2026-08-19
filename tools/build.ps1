# WPI build wrapper (ASCII only). Real logic is in tools/build.py (UTF-8 safe).
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
& python (Join-Path $Root "tools\build.py") @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }