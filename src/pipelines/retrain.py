"""Pipeline de réentraînement reproductible sans consommation du holdout externe.

Le jeu de test externe est volontairement absent de cette liste : il sert à la preuve
finale de certification et ne doit pas devenir un signal d'optimisation au fil des itérations.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys


# Étapes obligatoires exécutées dans l'ordre : préparation des données,
# sélection des features (sur TRAIN uniquement), puis entraînement.
BASE_STEPS = [
    [sys.executable, "-m", "src.data.prepare"],
    [sys.executable, "-m", "src.features.select_features"],
    [sys.executable, "-m", "src.models.train"],
]


def main(optimize: bool = False, trials: int = 30) -> None:
    """Orchestre le pipeline de réentraînement complet en exécutant chaque étape comme un sous-processus."""
    steps = []
    telemetry_bucket = os.getenv("PREDICTION_BUCKET")
    # Le feedback de production n'est intégré que si explicitement activé,
    # pour ne pas polluer un run standard avec des données non validées.
    if telemetry_bucket and os.getenv("INCLUDE_PRODUCTION_FEEDBACK", "0") == "1":
        steps.append([sys.executable, "-m", "src.data.collect_feedback", "--bucket", telemetry_bucket])
    steps.extend(BASE_STEPS)
    # L'optimisation d'hyperparamètres et la promotion du champion sont optionnelles
    # (coûteuses en temps) : activées uniquement via --optimize.
    if optimize:
        steps.append([sys.executable, "-m", "src.models.optimize", "--trials", str(trials)])
        steps.append([sys.executable, "-m", "src.models.promote"])
    steps.append([sys.executable, "-m", "src.models.quality_gate"])
    steps.append([sys.executable, "-m", "src.models.register"])

    for cmd in steps:
        print("RUN", " ".join(cmd), flush=True)
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--optimize", action="store_true")
    p.add_argument("--trials", type=int, default=30)
    args = p.parse_args()
    main(args.optimize, args.trials)
