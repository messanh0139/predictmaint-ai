#!/usr/bin/env python3
"""
Génère des prédictions pour peupler Grafana avec des métriques de drift
Usage: python scripts/generate_predictions_for_grafana.py --api-url http://localhost:8001
"""
import requests
import random
import time
import argparse

# Valeurs normales (référence)
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
    "sensor_21": 23.419
}


def generate_snapshot(drift_factor: float, cycle: int = 1) -> dict:
    """Génère un snapshot avec drift"""
    data = {"cycle": cycle}

    data["setting_1"] = BASELINE_VALUES["setting_1"] + random.uniform(-0.001, 0.001)
    data["setting_2"] = BASELINE_VALUES["setting_2"] + random.uniform(-0.0001, 0.0001)
    data["setting_3"] = BASELINE_VALUES["setting_3"]

    for i in range(1, 22):
        sensor_key = f"sensor_{i}"
        base_value = BASELINE_VALUES[sensor_key]
        noise = random.uniform(-0.05, 0.05)
        drift_offset = drift_factor * random.uniform(-1, 1)
        value = base_value * (1 + drift_offset + noise)
        data[sensor_key] = round(value, 4)

    return data


def send_prediction(api_url: str, engine_id: int, drift_factor: float) -> dict:
    """Envoie une prédiction"""
    payload = {
        "engine_id": engine_id,
        "history": [generate_snapshot(drift_factor, cycle=1)]
    }

    try:
        response = requests.post(
            f"{api_url}/predict",
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8001", help="API URL")
    parser.add_argument("--num", type=int, default=50, help="Nombre de prédictions")
    args = parser.parse_args()

    print("=" * 70)
    print("GÉNÉRATION DE PRÉDICTIONS POUR GRAFANA")
    print("=" * 70)
    print(f"API URL    : {args.api_url}")
    print(f"Prédictions: {args.num}")
    print("=" * 70)
    print()

    successes = 0
    failures = 0

    for i in range(args.num):
        engine_id = 5000 + i

        # Drift progressif de 0% à 30%
        progress = i / args.num
        drift_factor = progress * 0.30

        result = send_prediction(args.api_url, engine_id, drift_factor)

        if result["success"]:
            successes += 1
            pred_id = result["data"]["prediction_id"][:8]
            risk = result["data"]["risk"]
            print(f"[{i+1:3d}/{args.num}] OK {pred_id}... | Risk: {risk:4s} | Drift: {drift_factor:5.1%}")
        else:
            failures += 1
            print(f"[{i+1:3d}/{args.num}] ERREUR: {result['error']}")

        time.sleep(0.5)  # 0.5 seconde entre prédictions

    print()
    print("=" * 70)
    print(f"TERMINÉ : {successes} succès, {failures} échecs")
    print("=" * 70)
    print()
    print("Prochaines étapes :")
    print("1. Attendez 5-10 minutes (calcul du drift en arrière-plan)")
    print("2. Ouvrez Grafana : https://predictmaint-grafana-xxx.run.app")
    print("3. Dashboard : PredictMaint AI - Cloud Monitoring")
    print("4. Métriques visibles : drift_psi, drift_share")
    print()


if __name__ == "__main__":
    main()
