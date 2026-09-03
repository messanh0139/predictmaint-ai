from __future__ import annotations

import hashlib
import json
import os
import platform
from importlib import metadata as importlib_metadata
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    # Empreinte SHA256 d'un fichier, lu par blocs de 1 Mo pour rester sobre en mémoire sur les gros fichiers
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_sha() -> str:
    # SHA du commit courant : priorité à la variable d'environnement CI, sinon lecture via git localement
    if os.getenv("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        return "unknown"


def runtime_metadata() -> dict:
    # Capture l'environnement d'exécution (commit, python, OS, versions de packages) pour la traçabilité du modèle
    packages = {}
    for name in ["pandas", "numpy", "scikit-learn", "xgboost", "joblib"]:
        try:
            packages[name] = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            packages[name] = "not-installed"
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "package_versions": packages,
    }


def canonical_json_sha256(payload: dict) -> str:
    # Empreinte déterministe d'un dict : clés triées et séparateurs fixes pour un JSON reproductible entre runs
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
