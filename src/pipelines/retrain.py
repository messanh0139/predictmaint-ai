"""Pipeline de réentraînement reproductible sans consommation du holdout externe NASA.

Le test NASA est volontairement absent de cette liste : il sert à la preuve finale de
certification et ne doit pas devenir un signal d'optimisation au fil des itérations.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys


BASE_STEPS = [
    [sys.executable, "-m", "src.data.prepare"],
    [sys.executable, "-m", "src.features.select_features"],
    [sys.executable, "-m", "src.models.train"],
]


def main(optimize: bool = False, trials: int = 30) -> None:
    steps = []
    telemetry_bucket = os.getenv("PREDICTION_BUCKET")
    if telemetry_bucket and os.getenv("INCLUDE_PRODUCTION_FEEDBACK", "0") == "1":
        steps.append([sys.executable, "-m", "src.data.collect_feedback", "--bucket", telemetry_bucket])
    steps.extend(BASE_STEPS)
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
