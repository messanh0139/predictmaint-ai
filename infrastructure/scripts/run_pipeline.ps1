$ErrorActionPreference = "Stop"

if (Test-Path ".\venv\Scripts\Activate.ps1") {
    & .\venv\Scripts\Activate.ps1
} elseif (Test-Path ".\.venv\Scripts\Activate.ps1") {
    & .\.venv\Scripts\Activate.ps1
} else {
    throw "Aucun environnement virtuel venv/.venv trouvé. Exécutez d'abord .\scripts\setup.ps1"
}

python -m src.data.prepare
python -m src.features.select_features
python -m src.models.train
python -m src.models.optimize --trials 10
python -m src.models.promote
python -m src.models.quality_gate
python -m src.models.register

Write-Host "Development pipeline completed."
Write-Host "Le holdout NASA n'a pas été ouvert."
Write-Host "Pour l'évaluation externe finale uniquement :"
Write-Host "  python -m src.models.evaluate"
