#!/usr/bin/env python3
"""
Génération de données de démonstration avec drift progressif
Usage: python scripts/generate_demo_data_with_drift.py
Output: demo_data_with_drift.csv (prêt pour upload dashboard)
"""
import pandas as pd
import numpy as np
from pathlib import Path

# Valeurs moyennes issues du dataset FD001 (référence sans drift)
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


def generate_engine_cycles(engine_id: int, num_cycles: int, drift_factor: float, label: int) -> pd.DataFrame:
    """Génère les cycles pour un moteur avec drift appliqué"""
    rows = []

    for cycle in range(1, num_cycles + 1):
        row = {
            "engine_id": engine_id,
            "cycle": cycle,
        }

        # Settings avec légère variation
        row["setting_1"] = BASELINE_VALUES["setting_1"] + np.random.uniform(-0.001, 0.001)
        row["setting_2"] = BASELINE_VALUES["setting_2"] + np.random.uniform(-0.0001, 0.0001)
        row["setting_3"] = BASELINE_VALUES["setting_3"]

        # Sensors avec drift progressif + bruit
        for i in range(1, 22):
            sensor_key = f"sensor_{i}"
            base_value = BASELINE_VALUES[sensor_key]

            # Bruit aléatoire ±5%
            noise = np.random.uniform(-0.05, 0.05)

            # Drift appliqué (proportionnel au facteur)
            drift_offset = drift_factor * np.random.uniform(-1, 1)

            # Valeur finale
            value = base_value * (1 + drift_offset + noise)
            row[sensor_key] = round(value, 4)

        # Label : identique pour tous les cycles d'un même moteur
        row["actual_failure_within_30_cycles"] = label

        rows.append(row)

    return pd.DataFrame(rows)


def generate_demo_dataset(
    num_engines: int = 30,
    cycles_per_engine_range: tuple = (50, 150),
    drift_progression: str = "gradual"
) -> pd.DataFrame:
    """
    Génère un dataset complet avec drift progressif

    Args:
        num_engines: Nombre de moteurs à générer
        cycles_per_engine_range: (min, max) cycles par moteur
        drift_progression: "none", "gradual", "sudden"
    """
    all_data = []

    for engine_id in range(1000, 1000 + num_engines):
        # Nombre de cycles aléatoire pour ce moteur
        num_cycles = np.random.randint(cycles_per_engine_range[0], cycles_per_engine_range[1])

        # Label : alternance pour avoir des cas positifs et négatifs
        label = 1 if (engine_id % 3 == 0) else 0

        # Calcul du drift factor selon la progression
        if drift_progression == "none":
            drift_factor = 0.0
        elif drift_progression == "gradual":
            # Drift progressif de 0% à 40% sur l'ensemble des moteurs
            progress = (engine_id - 1000) / num_engines
            drift_factor = progress * 0.40
        elif drift_progression == "sudden":
            # Pas de drift pour la première moitié, puis drift fort
            if (engine_id - 1000) < (num_engines / 2):
                drift_factor = 0.0
            else:
                drift_factor = 0.35
        else:
            drift_factor = 0.0

        # Générer les cycles pour ce moteur
        engine_df = generate_engine_cycles(engine_id, num_cycles, drift_factor, label)
        all_data.append(engine_df)

    return pd.concat(all_data, ignore_index=True)


def main():
    print("=" * 70)
    print("GÉNÉRATION DE DONNÉES DE DÉMONSTRATION AVEC DRIFT")
    print("=" * 70)
    print()

    # Configuration
    NUM_ENGINES = 30
    DRIFT_TYPE = "gradual"  # Options: "none", "gradual", "sudden"

    print(f"Configuration :")
    print(f"  - Nombre de moteurs    : {NUM_ENGINES}")
    print(f"  - Cycles par moteur    : 50-150 (aléatoire)")
    print(f"  - Type de drift        : {DRIFT_TYPE}")
    print(f"  - Drift range          : 0% à 40% (progressif)")
    print()

    # Génération
    print("Génération en cours...")
    df = generate_demo_dataset(
        num_engines=NUM_ENGINES,
        cycles_per_engine_range=(50, 150),
        drift_progression=DRIFT_TYPE
    )

    # Statistiques
    print()
    print("Statistiques :")
    print(f"  - Lignes totales       : {len(df):,}")
    print(f"  - Moteurs uniques      : {df['engine_id'].nunique()}")
    print(f"  - Labels positifs (1)  : {(df['actual_failure_within_30_cycles'] == 1).sum():,} cycles")
    print(f"  - Labels négatifs (0)  : {(df['actual_failure_within_30_cycles'] == 0).sum():,} cycles")
    print()

    # Analyse du drift (sur les 5 premiers sensors)
    print("Aperçu du drift (moyennes par tranche de moteurs) :")
    df['engine_batch'] = pd.cut(df['engine_id'], bins=3, labels=['Début (0% drift)', 'Milieu (20% drift)', 'Fin (40% drift)'])

    for sensor in ['sensor_1', 'sensor_2', 'sensor_3']:
        means = df.groupby('engine_batch')[sensor].mean()
        print(f"  {sensor:10s} : {means.iloc[0]:8.2f} puis {means.iloc[1]:8.2f} puis {means.iloc[2]:8.2f}")

    df = df.drop(columns=['engine_batch'])
    print()

    # Sauvegarde
    output_path = Path("demo_data_with_drift.csv")
    df.to_csv(output_path, index=False)

    print("=" * 70)
    print(f"FICHIER GÉNÉRÉ : {output_path.resolve()}")
    print("=" * 70)
    print()
    print("Utilisation pour la démonstration :")
    print()
    print("1. DASHBOARD (Recommandé pour soutenance)")
    print("   - Ouvrir : https://predictmaint-dashboard-xxx.run.app")
    print("   - Onglet : Réentraînement automatique")
    print("   - Upload : demo_data_with_drift.csv")
    print("   - Observer : Déclenchement automatique + statut temps réel")
    print()
    print("2. API directe (via cURL)")
    print(f'   curl -X POST "https://predictmaint-api-xxx.run.app/retrain/upload" \\')
    print(f'     -F "file=@{output_path}"')
    print()
    print("3. Vérifier Grafana (5-10 min après)")
    print("   - URL : https://predictmaint-grafana-xxx.run.app")
    print("   - Dashboard : PredictMaint AI - Cloud Monitoring")
    print("   - Métriques : drift_psi, drift_share")
    print()


if __name__ == "__main__":
    main()
