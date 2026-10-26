# == SkipMan -- one-command push-live ========================================
# Usage (from Desktop\Superdev\BBProjectDevelopment\SkipMan):
#     .\update.ps1 "what you changed"
#
# Does, in order:
#   1. Compile-checks every skipman/*.py file (aborts on any error)
#   2. Mirrors this working copy into the git repo (Superdev\SongDL)
#   3. git add / commit / push to GitHub (Wabbilly/SkipMan)
#
# Rules live in README.md. Short version: edit HERE, never in SongDL.
# NOTE: keep this file ASCII-only. Fancy dashes/quotes break PowerShell 5.1.

param(
    [string]$Message = ""
)

$ErrorActionPreference = "Stop"
$Src  = $PSScriptRoot
$Repo = Join-Path $env:USERPROFILE "Desktop\Superdev\SongDL"

if (-not $Message) {
    $Message = "Update SkipMan ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))"
}

Write-Host ""
Write-Host "// SKIPMAN PUSH" -ForegroundColor Green
Write-Host "   src : $Src"
Write-Host "   repo: $Repo"
Write-Host ""

# -- 1. Compile check --------------------------------------------------------
Write-Host "[1/3] Compile check..." -ForegroundColor Yellow
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Write-Host "python not found on PATH." -ForegroundColor Red; exit 1 }

& python -m compileall -q (Join-Path $Src "skipman")
if ($LASTEXITCODE -ne 0) {
    Write-Host "COMPILE FAILED - fix the errors above. Nothing was pushed." -ForegroundColor Red
    exit 1
}
Write-Host "      OK" -ForegroundColor Green

# -- 2. Sync working copy -> repo --------------------------------------------
Write-Host "[2/3] Syncing to repo..." -ForegroundColor Yellow
if (-not (Test-Path (Join-Path $Repo ".git"))) {
    Write-Host "Git repo not found at $Repo" -ForegroundColor Red
    exit 1
}

# Package code: mirror (deletes files removed from the working copy)
robocopy (Join-Path $Src "skipman") (Join-Path $Repo "skipman") *.py /MIR /XD __pycache__ /NJH /NJS /NDL /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Write-Host "robocopy failed." -ForegroundColor Red; exit 1 }

# Top-level files
$topFiles = @("skipman.pyw", "SkipMan.bat", "SkipMan.vbs",
              "requirements.txt", "README.md", "CHANGELOG.md", "update.ps1")
foreach ($f in $topFiles) {
    $p = Join-Path $Src $f
    if (Test-Path $p) { Copy-Item $p (Join-Path $Repo $f) -Force }
}
Write-Host "      OK" -ForegroundColor Green

# -- 3. Commit + push --------------------------------------------------------
Write-Host "[3/3] Git commit + push..." -ForegroundColor Yellow
Push-Location $Repo
try {
    git add -A
    $pending = git status --porcelain
    if (-not $pending) {
        Write-Host "      Nothing new to commit." -ForegroundColor Green
    } else {
        git commit -m $Message | Out-Null
        Write-Host "      Committed: $Message" -ForegroundColor Green
    }
    # Always push - catches commits made earlier that never went out
    git push origin master
    if ($LASTEXITCODE -ne 0) {
        Write-Host "PUSH FAILED - commit is saved locally; run 'git push' in $Repo when back online." -ForegroundColor Red
        exit 1
    }
    Write-Host "      GitHub is up to date." -ForegroundColor Green
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "DONE. Everything is live." -ForegroundColor Green
