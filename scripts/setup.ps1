$ErrorActionPreference = "Stop"

if (-not (Test-Path "venv")) {
    py -m venv venv
}

& .\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -c constraints-model.txt
Write-Host "Environment ready: venv"
