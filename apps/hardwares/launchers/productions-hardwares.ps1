$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..\..")
Set-Location $ProjectRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv is not installed or not available on PATH."
    Write-Host "Install uv first, then run this launcher again."
    Read-Host "Press Enter to close"
    exit 1
}

uv run --package productions-hardwares productions-hardwares
$Status = $LASTEXITCODE

Write-Host ""
if ($Status -ne 0) {
    Write-Host "productions-hardwares exited with code $Status"
}
Read-Host "Press Enter to close"
exit $Status
