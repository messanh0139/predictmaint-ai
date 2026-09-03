from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import REFERENCE_DIR, ROOT


def psi(reference: pd.Series, current: pd.Series, bins: int = 10) -> float:
    # Population Stability Index avec bornes apprises sur la référence uniquement
    ref = pd.to_numeric(reference, errors="coerce").dropna().to_numpy()
    cur = pd.to_numeric(current, errors="coerce").dropna().to_numpy()
    if len(ref) < 20 or len(cur) < 20:
        return 0.0
    quantiles = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(quantiles) < 3:
        return 0.0
    # Bornes extrêmes ouvertes : toute valeur future hors de la plage de référence
    # tombe quand même dans le premier ou dernier bin au lieu d'être perdue.
    quantiles[0] = -np.inf
    quantiles[-1] = np.inf
    ref_hist, _ = np.histogram(ref, bins=quantiles)
    cur_hist, _ = np.histogram(cur, bins=quantiles)
    eps = 1e-6
    ref_p = np.clip(ref_hist / max(ref_hist.sum(), 1), eps, None)
    cur_p = np.clip(cur_hist / max(cur_hist.sum(), 1), eps, None)
    return float(np.sum((cur_p - ref_p) * np.log(cur_p / ref_p)))


def statistical_drift_report(
    current: pd.DataFrame,
    reference: pd.DataFrame | None = None,
    psi_threshold: float = 0.20,
    min_samples: int = 20,
) -> dict:
    # Compare la distribution courante à la référence (PSI par feature) et agrège un statut d'alerte
    if reference is None:
        reference = pd.read_csv(REFERENCE_DIR / "reference_features.csv")

    common = [c for c in reference.columns if c in current.columns]
    base = {
        "reference_rows": int(len(reference)),
        "current_rows": int(len(current)),
        "min_samples": int(min_samples),
        "psi_threshold": float(psi_threshold),
        "features_checked": len(common),
    }
    if len(reference) < min_samples or len(current) < min_samples:
        return {
            **base,
            "drifted_features": {},
            "drifted_share": None,
            "status": "insufficient_data",
            "psi_by_feature": {},
        }
    if not common:
        return {
            **base,
            "drifted_features": {},
            "drifted_share": None,
            "status": "invalid_schema",
            "psi_by_feature": {},
        }

    values = {c: psi(reference[c], current[c]) for c in common}
    drifted = {c: v for c, v in values.items() if v >= psi_threshold}
    share = len(drifted) / max(len(values), 1)
    return {
        **base,
        "drifted_features": drifted,
        "drifted_share": share,
        # Alerte globale si au moins 20% des features ont dérivé, indépendamment du seuil PSI par feature.
        "status": "alert" if share >= 0.20 else "ok",
        "psi_by_feature": values,
    }


def current_features_from_prediction_log(path: str | Path) -> pd.DataFrame:
    # Reconstruit un DataFrame de features à partir des snapshots stockés dans le log de prédictions (JSONL)
    rows = []
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    with p.open(encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            if record.get("feature_snapshot"):
                rows.append(record["feature_snapshot"])
    return pd.DataFrame(rows)


def generate_evidently_report(current: pd.DataFrame, output_path: str | Path) -> Path | None:
    # Génère un rapport HTML de drift via evidently, si la dépendance optionnelle est installée
    try:
        from evidently import Report
        from evidently.presets import DataDriftPreset
    except Exception:
        # Dépendance optionnelle : on n'échoue pas si evidently n'est pas installé.
        return None
    reference = pd.read_csv(REFERENCE_DIR / "reference_features.csv")
    common = [c for c in reference.columns if c in current.columns]
    if not common or len(current) < 20:
        return None
    report = Report([DataDriftPreset()])
    result = report.run(reference_data=reference[common], current_data=current[common])
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save_html(str(output))
    return output


def main() -> None:
    # CLI : calcule le rapport de drift statistique (et le rapport HTML evidently si possible)
    p = argparse.ArgumentParser()
    p.add_argument("current", help="CSV de features ou fichier predictions.jsonl")
    p.add_argument("--jsonl", action="store_true")
    p.add_argument("--output-json", default=str(ROOT / "monitoring/evidently/reports/drift_metrics.json"))
    p.add_argument("--output-html", default=str(ROOT / "monitoring/evidently/reports/drift_report.html"))
    args = p.parse_args()

    current = current_features_from_prediction_log(args.current) if args.jsonl else pd.read_csv(args.current)
    result = statistical_drift_report(current)
    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    html = generate_evidently_report(current, args.output_html)
    result["evidently_html"] = str(html) if html else None
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
