#!/usr/bin/env python3
"""
Envoie des prédictions puis leur feedback à l'API, comme un vrai client.
Le prochain retrain les récupère automatiquement (collect_feedback.py).

Usage:
  python scripts/generate_production_feedback.py \
      --api-url https://predictmaint-api-6iao6qpasa-ew.a.run.app \
      --num 20
"""
import argparse
import random
import time

import requests

BASELINE_VALUES = {
    "setting_1": 0.0015,
    "setting_2": 0.0003,
    "setting_3": 100.0,
    "sensor_1": 518.67,
    "sensor_2": 641.82,
    "sensor_3": 1589.7,
    "sensor_4": 1400.6,
    "sensor_5": 14.62,
    "sensor_6": 21.61,
    "sensor_7": 554.36,
    "sensor_8": 2388.06,
    "sensor_9": 9046.19,
    "sensor_10": 1.3,
    "sensor_11": 47.47,
    "sensor_12": 521.66,
    "sensor_13": 2388.02,
    "sensor_14": 8138.62,
    "sensor_15": 8.4195,
    "sensor_16": 0.03,
    "sensor_17": 392,
    "sensor_18": 2388,
    "sensor_19": 100.0,
    "sensor_20": 39.06,
    "sensor_21": 23.419,
}


def build_history(num_cycles: int, failing: bool) -> list[dict]:
    # trajectoire plate si le moteur est sain, dégradation progressive sinon
    history = []
    for cycle in range(1, num_cycles + 1):
        progress = cycle / num_cycles
        degradation = progress**2 * 0.35 if failing else 0.0
        snap = {
            "cycle": cycle,
            "setting_1": BASELINE_VALUES["setting_1"] + random.uniform(-0.001, 0.001),
            "setting_2": BASELINE_VALUES["setting_2"] + random.uniform(-0.0001, 0.0001),
            "setting_3": BASELINE_VALUES["setting_3"],
        }
        for i in range(1, 22):
            key = f"sensor_{i}"
            base = BASELINE_VALUES[key]
            noise = random.uniform(-0.03, 0.03)
            snap[key] = round(base * (1 + degradation * random.uniform(0.7, 1.3) + noise), 4)
        history.append(snap)
    return history


def main() -> None:
    # point d'entrée CLI : envoie les prédictions/feedback aux moteurs synthétiques
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True, help="URL de l'API de production")
    parser.add_argument("--num", type=int, default=20, help="Nombre de moteurs synthétiques")
    parser.add_argument("--engine-id-start", type=int, default=501)
    parser.add_argument("--failure-ratio", type=float, default=0.3)
    args = parser.parse_args()

    print(f"Injection de {args.num} moteurs synthétiques via {args.api_url}")
    ok, ko = 0, 0
    for i in range(args.num):
        engine_id = args.engine_id_start + i
        failing = random.random() < args.failure_ratio
        history = build_history(random.randint(15, 40), failing)

        pred_resp = requests.post(
            f"{args.api_url}/predict",
            json={"engine_id": engine_id, "history": history},
            timeout=15,
        )
        if pred_resp.status_code != 200:
            print(f"[{i+1}/{args.num}] engine {engine_id}: /predict a échoué ({pred_resp.status_code})")
            ko += 1
            continue
        prediction_id = pred_resp.json()["prediction_id"]

        fb_resp = requests.post(
            f"{args.api_url}/feedback",
            json={
                "prediction_id": prediction_id,
                "actual_failure_within_30_cycles": int(failing),
            },
            timeout=15,
        )
        if fb_resp.status_code != 200:
            print(f"[{i+1}/{args.num}] engine {engine_id}: /feedback a échoué ({fb_resp.status_code})")
            ko += 1
            continue

        ok += 1
        print(
            f"[{i+1}/{args.num}] engine {engine_id}: prediction {prediction_id[:8]}... "
            f"label={'FAILURE' if failing else 'OK'} risk={pred_resp.json()['risk']}"
        )
        time.sleep(0.3)

    print()
    print(f"Terminé : {ok} moteurs labellisés injectés, {ko} échecs.")
    print("Ces données seront reprises automatiquement par collect_feedback.py")
    print("au prochain déclenchement du pipeline (push sur main, ou :")
    print("  gh workflow run deploy.yml")
    print(")")


if __name__ == "__main__":
    main()
