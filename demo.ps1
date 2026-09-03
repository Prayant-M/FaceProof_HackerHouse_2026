# FaceProof demo driver -- the exact sequence used in the screen recording.
#
#   .\demo.ps1 -Image samples\me.jpg -Chain local
#   .\demo.ps1 -Image samples\me.jpg -Chain base-sepolia
#
# Runs each stage as a separate command with a pause between, so every step is
# visible on camera instead of scrolling past.

param(
    [string]$Image = "samples\me.jpg",
    [ValidateSet("local", "base-sepolia", "sepolia")]
    [string]$Chain = "local",
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
if (Test-Path ".venv\Scripts\Activate.ps1") { & .\.venv\Scripts\Activate.ps1 }

function Beat($label) {
    Write-Host ""
    Write-Host ("-" * 70) -ForegroundColor DarkGray
    Write-Host "  $label" -ForegroundColor Cyan
    Write-Host ("-" * 70) -ForegroundColor DarkGray
    if (-not $NoPause) { Read-Host "  [enter to continue]" | Out-Null }
    Clear-Host
}

Beat "1/6  environment"
python -m faceproof info

Beat "2/6  face scan"
python -m faceproof scan --image $Image
$scan = (Get-ChildItem out\scan_*.json | Sort-Object LastWriteTime -Desc | Select-Object -First 1)
$scanId = $scan.BaseName -replace '^scan_', ''
Write-Host "scan id: $scanId"

Beat "3/6  live web/social search + adversarial re-rank"
python -m faceproof search --scan $scanId

Beat "4/6  anchor on $Chain"
python -m faceproof anchor --evidence $scanId --chain $Chain

Beat "5/6  re-verify against the chain"
python -m faceproof verify --evidence $scanId --chain $Chain

Beat "6/6  tamper demo -- one character"
python -m faceproof tamper-demo --evidence $scanId --chain $Chain

Write-Host ""
Write-Host "Demo complete. Evidence: out\ev_$scanId.json" -ForegroundColor Green
