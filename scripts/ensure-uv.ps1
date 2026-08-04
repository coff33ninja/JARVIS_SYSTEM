param(
    [switch]$InstallMissing,
    [switch]$ManagedPython,
    [string]$PythonVersion = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Continue"

function Write-Status { param([string]$Label, [bool]$Ok)
    $icon = if ($Ok) { "[+]" } else { "[-]" }
    Write-Host "$icon $Label"
}

function Test-Command { param([string]$Name)
    $null = Get-Command $Name -ErrorAction SilentlyContinue; return $?
}

function Get-UserPath {
    [Environment]::GetEnvironmentVariable("PATH","User")
}

function Add-ToUserPath { param([string]$Dir)
    $userPath = Get-UserPath
    if ($userPath -notlike "*$Dir*") {
        [Environment]::SetEnvironmentVariable("PATH","$Dir;$userPath","User")
        $env:Path = "$Dir;$env:Path"
        return $true
    }
    return $false
}

Write-Host "=== uv (Python Package Manager) ===" -ForegroundColor Cyan

$results = @()

# Check uv
$uvInstallDir = "$env:USERPROFILE\.local\bin"
$uvLocalPath = Join-Path $uvInstallDir "uv.exe"
$uvFound = (Test-Command "uv") -or (Test-Path $uvLocalPath)
Write-Status "uv installed" $uvFound
$results += @{Name="uv"; Found=$uvFound}

# Check Python
$pythonFound = Test-Command "python"
Write-Status "Python available" $pythonFound
$results += @{Name="Python"; Found=$pythonFound}

if ($uvFound -and (Test-Command "uv")) {
    $uvVer = & uv --version 2>$null
    Write-Host "     uv version: $uvVer" -ForegroundColor DarkGray

    # Check uv-managed Python
    $managed = & uv python list 2>$null | Select-Object -First 1
    if ($managed) {
        Write-Status "uv-managed Python" $true
        Write-Host "     $managed" -ForegroundColor DarkGray
    } else {
        Write-Status "uv-managed Python" $false
    }
}

$any = ($results | Where-Object { $_.Found }).Count
Write-Host "$any of $($results.Count) checks passed." -ForegroundColor Cyan

if ($InstallMissing) {
    # Install uv
    if (-not $uvFound) {
        Write-Host "Installing uv..." -ForegroundColor Yellow
        if ($DryRun) { Write-Host "[DRY-RUN] Would run: irm https://astral.sh/uv/install.ps1 | iex"; exit 0 }
        try {
            $installScript = Invoke-RestMethod -Uri "https://astral.sh/uv/install.ps1" -TimeoutSec 30 -UseBasicParsing
            Invoke-Expression $installScript
            if (Test-Path $uvLocalPath) {
                $added = Add-ToUserPath $uvInstallDir
                Write-Host "[+] uv installed to $uvInstallDir" -ForegroundColor Green
            } else {
                Write-Host "[ERROR] uv install completed but binary not found at $uvLocalPath" -ForegroundColor Red
                exit 1
            }
        } catch {
            Write-Host "[ERROR] uv install failed: $_" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "    uv already installed, skipping." -ForegroundColor DarkGray
    }

    # Install managed Python
    if ($ManagedPython -or $PythonVersion) {
        $ver = if ($PythonVersion) { $PythonVersion } else { "3.12" }
        Write-Host "Installing uv-managed Python $ver..." -ForegroundColor Yellow
        if ($DryRun) { Write-Host "[DRY-RUN] Would run: uv python install $ver"; exit 0 }
        try {
            & uv python install $ver 2>&1 | Out-String | Write-Host
            Write-Host "[+] Python $ver installed via uv" -ForegroundColor Green
        } catch {
            Write-Host "[ERROR] Python $ver install failed: $_" -ForegroundColor Red
            exit 1
        }
    }
}

Write-Host ""
Write-Host "Quick start: cd project && uv init && uv add requests" -ForegroundColor Cyan
