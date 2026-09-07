# FaceProof one-shot setup (Windows / PowerShell)
#
#   .\setup.ps1
#
# Creates a Python 3.12 (or 3.11) venv, installs dependencies, pre-downloads
# the InsightFace models, and copies .env.example to .env.
#
# Safe to re-run: it skips the venv and .env if they already exist.
#
# insightface has no wheel on any Python version -- it compiles Cython C
# extensions, so Microsoft C++ Build Tools must be installed:
#   winget install Microsoft.VisualStudio.2022.BuildTools --override `
#     "--wait --quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"

$ErrorActionPreference = "Stop"

Write-Host "== FaceProof setup ==" -ForegroundColor Cyan

# --- 1. Python venv ----------------------------------------------------------
# 3.12 and 3.11 both work. 3.13/3.14 do NOT -- onnxruntime publishes no wheels
# for them and pip falls back to building from source.
if (-not (Test-Path ".venv")) {
    $tag = $null
    $exe = $null
    foreach ($candidate in @("3.12", "3.11")) {
        try { $found = (py -$candidate -c "import sys; print(sys.executable)" 2>$null) } catch { $found = $null }
        if ($found) { $tag = $candidate; $exe = $found; break }
    }
    if (-not $tag) {
        Write-Host "No supported Python found (need 3.12 or 3.11)." -ForegroundColor Yellow
        Write-Host "Install one, then re-run:  winget install Python.Python.3.12"
        Write-Host "(3.13/3.14 will NOT work -- onnxruntime has no wheels for them.)"
        exit 1
    }
    Write-Host "creating venv with Python $tag -- $exe"
    py -$tag -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

# --- 2. dependencies ---------------------------------------------------------
Write-Host "`ninstalling dependencies (this pulls ~400 MB)..." -ForegroundColor Cyan
pip install -r requirements.txt

# --- 3. models ---------------------------------------------------------------
Write-Host "`npre-downloading InsightFace models..." -ForegroundColor Cyan
python scripts/fetch_models.py

# --- 4. env ------------------------------------------------------------------
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "`ncreated .env -- fill in SERPAPI_KEY and PRIVATE_KEY" -ForegroundColor Yellow
}

Write-Host "`nDone." -ForegroundColor Green
Write-Host "Next:"
Write-Host "  1. edit .env             (SERPAPI_KEY, PRIVATE_KEY)"
Write-Host "  2. npx hardhat node      (in a second terminal, for --chain local)"
Write-Host "  3. python scripts/deploy.py --chain local"
Write-Host "  4. python -m faceproof run --image samples/me.jpg --chain local --i-have-consent"
