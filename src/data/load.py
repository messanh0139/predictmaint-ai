from pathlib import Path
import pandas as pd

from src.config import BASE_COLUMNS, RAW_DIR


def _read_space_file(path: Path, names: list[str]) -> pd.DataFrame:
    return pd.read_csv(path, sep=r"\s+", header=None, names=names)


def load_train_fd001(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Charge uniquement le jeu d'entraînement utilisé pour le développement.

    Cette fonction est utilisée par le pipeline standard afin de ne pas ouvrir le
    holdout externe pendant la préparation, le tuning ou le retraining.
    """
    return _read_space_file(raw_dir / "train_FD001.txt", BASE_COLUMNS)


def load_test_inputs_fd001(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Charge seulement les entrées du jeu de test externe, sans vérité terrain."""
    return _read_space_file(raw_dir / "test_FD001.txt", BASE_COLUMNS)


def load_external_test_fd001(
    raw_dir: Path = RAW_DIR,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Charge le holdout externe et sa vérité terrain.

    À appeler uniquement lors d'une évaluation externe explicite/finale.
    """
    test = load_test_inputs_fd001(raw_dir)
    rul = pd.read_csv(
        raw_dir / "RUL_FD001.txt",
        sep=r"\s+",
        header=None,
        names=["RUL_at_last_observation"],
    )
    return test, rul


def load_fd001(
    raw_dir: Path = RAW_DIR,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compatibilité historique : charge train + holdout.

    Préférer `load_train_fd001()` dans les pipelines de développement et
    `load_external_test_fd001()` seulement dans l'évaluation externe.
    """
    train = load_train_fd001(raw_dir)
    test, rul = load_external_test_fd001(raw_dir)
    return train, test, rul
