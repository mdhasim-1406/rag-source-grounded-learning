# Scholar Studio - Windows Native Startup Script
# Requires PowerShell 5.1+
[CmdletBinding()]
param(
    [Alias("H", "host")]
    [string]$HostName,

    [Alias("p", "port")]
    [string]$Port,

    [switch]$Reload
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

# 1. Ensure virtual environment exists
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[start] Virtual environment not found or incomplete. Running setup.ps1..." -ForegroundColor Yellow
    & (Join-Path $ProjectRoot "setup.ps1")
}

# 2. Prefer dedicated cross-platform launcher if present
$Launcher = Join-Path $ProjectRoot "scripts\launcher.py"
if (Test-Path $Launcher) {
    $passArgs = @()
    if ($HostName) { $passArgs += @("--host", $HostName) }
    if ($Port) { $passArgs += @("--port", $Port) }
    if ($Reload) { $passArgs += @("--reload") }
    
    # Forward any unparsed/extra arguments
    if ($args) { $passArgs += $args }
    
    & "$VenvPython" "$Launcher" @passArgs
    exit $LASTEXITCODE
}

# 3. Fallback direct execution if launcher.py is absent
$EnvFile = Join-Path $ProjectRoot ".env"
$envHost = $null
$envPort = $null

if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -match '^HOST\s*=\s*(.*)$') {
            $envHost = $matches[1].Trim('"'' ')
        }
        if ($line -match '^PORT\s*=\s*(.*)$') {
            $envPort = $matches[1].Trim('"'' ')
        }
    }
}

$effectiveHost = if ($HostName) { $HostName } elseif ($env:HOST) { $env:HOST } elseif ($envHost) { $envHost } else { "127.0.0.1" }
$effectivePort = if ($Port) { $Port } elseif ($env:PORT) { $env:PORT } elseif ($envPort) { $envPort } else { "8000" }

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " Scholar Studio - Source-Grounded Learning System" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

if ($effectiveHost -eq "0.0.0.0" -or $effectiveHost -eq "::") {
    Write-Warning "[WARNING] Binding to 0.0.0.0 exposes Scholar Studio to your local network (LAN)."
    Write-Warning "[WARNING] This application is single-user with no built-in authentication."
    Write-Warning "[WARNING] Anyone on your local network can access the API and stored documents."
    Write-Warning "[WARNING] Ensure host firewall rules are applied. No automatic public tunnel is created."
    Write-Host "Local Access URL:  http://127.0.0.1:${effectivePort}" -ForegroundColor Green
} else {
    Write-Host "Local Access URL:  http://${effectiveHost}:${effectivePort}" -ForegroundColor Green
}

Write-Host "Health Endpoint:   http://127.0.0.1:${effectivePort}/health" -ForegroundColor Cyan
Write-Host "System Info:       http://127.0.0.1:${effectivePort}/api/v1/system" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

$uvicornArgs = @("-m", "uvicorn", "app.main:app", "--host", $effectiveHost, "--port", $effectivePort)
if ($Reload) { $uvicornArgs += "--reload" }

& "$VenvPython" @uvicornArgs
