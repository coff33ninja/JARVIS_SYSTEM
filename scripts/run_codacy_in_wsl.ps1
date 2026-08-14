<#!># PowerShell script to download and run Codacy Analysis CLI inside WSL.
<#
Usage:
  .\run_codacy_in_wsl.ps1 [-Distro Ubuntu-24.04] [-Tool bandit] [-Format text] [-OutFile /tmp/codacy/out.json] [-WindowsOutFile .\scripts\codacy_out.json]

What it does:
  - Downloads codacy-analysis-cli jar into /tmp/codacy in the specified WSL distro
  - Installs Java (default-jre-headless) inside WSL (uses sudo)
  - Runs `codacy.jar analyze` against the current Windows repo folder (translates to WSL path)
  - Optionally writes JSON/text output back to a Windows path

Notes:
  - Requires WSL and a distro with sudo access.
  - Run this from the repository root for correct default behavior.
#>

param(
    [string]$Distro = 'Ubuntu-24.04',
    [string]$Tool = 'bandit',
    [ValidateSet('text', 'json', 'sarif')][string]$Format = 'text',
    [string]$OutFile = '/tmp/codacy/out.json',
    [string]$WindowsOutFile = "$PSScriptRoot\codacy_out.json",
    [string]$ReleaseUrl = 'https://github.com/codacy/codacy-analysis-cli/releases/download/7.10.1/codacy-analysis-cli-assembly.jar'
)

Write-Host "Running Codacy analysis in WSL distro: $Distro" -ForegroundColor Cyan

# Resolve current repo path and convert to WSL path
$repoPath = (Resolve-Path -LiteralPath .).Path
Write-Host "Local repo path: $repoPath"

Write-Host "Converting Windows path to WSL path (best-effort) ..."
# Best-effort conversion without calling into WSL's wslpath (avoids quoting issues).
try {
    $driveLetter = $repoPath.Substring(0, 1).ToLower()
    $pathRest = $repoPath.Substring(2) -replace "\\", "/"
    $wslRepo = "/mnt/$driveLetter/$pathRest"
    Write-Host "WSL repo path: $wslRepo"
}
catch {
    Write-Warning "Failed to convert path locally, falling back to wslpath call."
    $wslRepo = wsl -d $Distro -- wslpath -a -u "$repoPath" 2>$null
    if (-not $?) {
        Write-Error "Failed to convert path to WSL. Is WSL and the distro '$Distro' available? Run 'wsl -l -v' to check."
        exit 2
    }
    $wslRepo = $wslRepo.Trim()
    Write-Host "WSL repo path: $wslRepo"
}

Write-Host "Creating /tmp/codacy and downloading codacy CLI inside WSL..."
wsl -d $Distro -- bash -lc "set -e; mkdir -p /tmp/codacy && cd /tmp/codacy && echo 'Downloading $ReleaseUrl' && curl -sSL -o codacy.jar '$ReleaseUrl' || exit 0"

Write-Host "Ensuring Java runtime in WSL (may prompt for sudo password)..."
wsl -d $Distro -- bash -lc "set -e; sudo apt-get update -y >/dev/null && sudo apt-get install -y default-jre-headless >/dev/null || true"

Write-Host "Running Codacy analysis (tool=$Tool, format=$Format) against: $wslRepo"
wsl -d $Distro -- bash -lc "set -e; cd /tmp/codacy; java -jar codacy.jar analyze -t $Tool -d '$wslRepo' -f $Format -o '$OutFile' || true"

Write-Host "If output exists in WSL, copying back to Windows path: $WindowsOutFile"
# Stream the file content from WSL to Windows file
wsl -d $Distro -- bash -lc "if [ -f '$OutFile' ]; then cat '$OutFile'; fi" | Out-File -Encoding utf8 -FilePath $WindowsOutFile

Write-Host "Done. WSL output (if any) written to: $WindowsOutFile" -ForegroundColor Green

Write-Host "Tip: you can also inspect WSL file directly at: \\wsl$\$Distro\tmp\codacy\" -ForegroundColor DarkYellow
