# Sigma Studio - Windows Installation Script
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location -Path (Split-Path -Parent $ScriptDir)

Write-Host "[SIGMA] Starting Windows Installation..." -ForegroundColor Cyan

# Check for Python
$pythonExists = Get-Command "python" -ErrorAction SilentlyContinue
if (-not $pythonExists) {
    Write-Host "[SIGMA] ERROR: Python 3.10+ is required but not found." -ForegroundColor Red
    Write-Host "[SIGMA] Suggestion: Install via Winget:" -ForegroundColor Yellow
    Write-Host "winget install Python.Python.3.11" -ForegroundColor Yellow
    exit 1
}

# Check for Node.js/npm
$npmExists = Get-Command "npm" -ErrorAction SilentlyContinue
if (-not $npmExists) {
    Write-Host "[SIGMA] ERROR: Node.js/npm is required but not found." -ForegroundColor Red
    Write-Host "[SIGMA] Suggestion: Install via Winget:" -ForegroundColor Yellow
    Write-Host "winget install OpenJS.NodeJS" -ForegroundColor Yellow
    exit 1
}

Write-Host "[SIGMA] System dependencies met. Running python installer..." -ForegroundColor Green
python sigma_launcher.py --install
