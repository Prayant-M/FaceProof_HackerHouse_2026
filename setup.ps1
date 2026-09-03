# FaceProof one-shot setup (Windows / PowerShell)
#
#   .\setup.ps1
#
# Creates a Python 3.11 venv, installs dependencies, pre-downloads the
# InsightFace models, and copies .env.example to .env.

$ErrorActionPreference = "Stop"

Write-Host "== FaceProof setup ==" -ForegroundColor Cyan

# --- 1. Python 3.11 venv -----------------------------------------------------
if (-not (Test-Path ".venv")) {
    $py311 = $null
    try { $py311 = (py -3.11 -c "import sys; print(sys.executable)") } catch {}
    if (-not $py311) {
        Write-Host "Python 3.11 not found." -ForegroundColor Yellow
        Write-Host "Install it, then re-run:  winget install Python.Python.3.11"
        Write-Host "(3.13/3.14 will NOT work -- onnxruntime and insightface have no wheels yet.)"
        exit 1
    }
    Write-Host "creating venv with $py311"
    py -3.11 -m venv .venv
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
