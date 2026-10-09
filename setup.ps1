# Scholar Studio - Windows Native Setup Script
# Requires PowerShell 5.1+ and Python >= 3.11 (or uv)
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " Scholar Studio - Windows Environment Setup" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# 1. Detect Python >= 3.11 or uv
$hasUv = [bool](Get-Command uv.exe -ErrorAction SilentlyContinue)
$selectedPython = $null
$selectedArgs = @()

if ($hasUv) {
    $uvVer = (uv.exe --version 2>&1)
    Write-Host "[setup] Found uv: $uvVer" -ForegroundColor Green
}

# Candidate python interpreters
$candidates = @(
    @{ Name = "python.exe"; Args = @() },
    @{ Name = "py.exe"; Args = @("-3") },
    @{ Name = "python3.exe"; Args = @() }
)

foreach ($cand in $candidates) {
    if (Get-Command $cand.Name -ErrorAction SilentlyContinue) {
        try {
            $check = & $cand.Name @($cand.Args) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'); sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $check) {
                $selectedPython = $cand.Name
                $selectedArgs = $cand.Args
                $pyVersion = $check.Trim()
                Write-Host "[setup] Detected supported Python runtime: $($cand.Name) ($pyVersion)" -ForegroundColor Green
                break
            }
        } catch {
            # Continue checking next candidate
        }
    }
}

if (-not $hasUv -and -not $selectedPython) {
    Write-Error "[setup] ERROR: Python >= 3.11 is required, but none was found on PATH. Please install Python 3.11+ (python.org) or uv (astral.sh/uv)."
    exit 1
}

# 2. Create virtual environment if not already present
$VenvDir = Join-Path $ProjectRoot ".venv"
if (-not (Test-Path $VenvDir)) {
    Write-Host "[setup] Creating virtual environment at .venv..." -ForegroundColor Cyan
    if ($hasUv) {
        uv.exe venv "$VenvDir"
    } else {
        & $selectedPython @selectedArgs -m venv "$VenvDir"
    }
} else {
    Write-Host "[setup] Virtual environment already exists at .venv." -ForegroundColor Yellow
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "[setup] ERROR: Virtual environment Python not found at $VenvPython"
    exit 1
}

# 3. Install backend package and dependencies
$BackendDir = Join-Path $ProjectRoot "backend"
Write-Host "[setup] Installing backend package and dependencies..." -ForegroundColor Cyan
if ($hasUv) {
    uv.exe pip install --python "$VenvPython" -e "$BackendDir"
} else {
    & $VenvPip install -e "$BackendDir"
}

# 4. Copy .env.example ONLY if .env does not already exist (never overwrite secrets/database)
$EnvFile = Join-Path $ProjectRoot ".env"
$EnvExample = Join-Path $ProjectRoot ".env.example"

if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Write-Host "[setup] Creating .env from .env.example with safe defaults..." -ForegroundColor Green
        Copy-Item -Path $EnvExample -Destination $EnvFile
    } else {
        Write-Warning "[setup] .env.example not found. Skipping .env creation."
    }
} else {
    Write-Host "[setup] Existing .env file found; preserving without changes." -ForegroundColor Yellow
}

# 5. Ensure data storage directory exists (never touches or overwrites existing database)
$DataUploads = Join-Path $ProjectRoot "data\uploads"
if (-not (Test-Path $DataUploads)) {
    New-Item -ItemType Directory -Path $DataUploads -Force | Out-Null
}

# 6. Verify backend package import
Write-Host "[setup] Verifying backend installation..." -ForegroundColor Cyan
& $VenvPython -c "import app.main; print('[setup] Verification passed: app.main loaded successfully.')"

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " Setup complete!" -ForegroundColor Green
Write-Host " Next steps:" -ForegroundColor Cyan
Write-Host "   1. Review or configure LLM provider settings in .env"
Write-Host "   2. Start server: .\start.ps1"
Write-Host "================================================================" -ForegroundColor Cyan
