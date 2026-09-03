$ErrorActionPreference = "Stop"

if (Test-Path ".\venv\Scripts\Activate.ps1") {
    & .\venv\Scripts\Activate.ps1
} elseif (Test-Path ".\.venv\Scripts\Activate.ps1") {
    & .\.venv\Scripts\Activate.ps1
} else {
    throw "Aucun environnement virtuel venv/.venv trouvé. Exécutez d'abord le setup."
}

python -m jupyter lab
