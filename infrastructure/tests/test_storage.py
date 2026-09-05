import json
import sys
import types
from unittest.mock import MagicMock

import pytest

from src.storage.model_artifacts import upload_champion_to_gcs


class _FakeBlob:
    # imite un blob GCS, mais stocke tout dans un simple dict en mémoire
    def __init__(self, store: dict, name: str):
        self._store = store
        self._name = name

    def exists(self) -> bool:
        # vrai si un fichier a déjà été écrit sous ce nom
        return self._name in self._store

    def download_as_text(self) -> str:
        # relit le contenu stocké
        return self._store[self._name]

    def upload_from_filename(self, path: str) -> None:
        # lit un fichier local et le garde en mémoire
        self._store[self._name] = open(path, encoding="utf-8").read()

    def upload_from_string(self, data: str, content_type: str | None = None) -> None:
        # garde le texte donné en mémoire
        self._store[self._name] = data


class _FakeBucket:
    # imite un bucket GCS, renvoie des _FakeBlob liés au même dict
    def __init__(self, store: dict):
        self._store = store

    def blob(self, name: str) -> _FakeBlob:
        # renvoie un blob lié au même dict, comme le ferait un vrai bucket
        return _FakeBlob(self._store, name)


def _install_fake_gcs(monkeypatch, store: dict) -> None:
    # remplace google.cloud.storage par notre fausse implémentation
    fake_bucket = _FakeBucket(store)
    fake_client = MagicMock()
    fake_client.bucket.return_value = fake_bucket
    fake_storage_module = types.SimpleNamespace(Client=MagicMock(return_value=fake_client))
    fake_google_cloud = types.SimpleNamespace(storage=fake_storage_module)
    monkeypatch.setitem(sys.modules, "google.cloud", fake_google_cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.storage", fake_storage_module)


def _write_model_files(tmp_path, validation_metrics: dict, version: str):
    # crée un faux model.joblib et son model_metadata.json pour les tests
    tmp_path.mkdir(parents=True, exist_ok=True)
    model_path = tmp_path / "model.joblib"
    model_path.write_bytes(b"fake-model")
    metadata_path = tmp_path / "model_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "model_version": version,
                "model_name": "xgboost_optimized",
                "validation_metrics": validation_metrics,
            }
        ),
        encoding="utf-8",
    )
    return model_path, metadata_path


GOOD_METRICS = {"recall": 1.0, "pr_auc": 0.95, "business_cost_per_1000": 50000.0, "brier": 0.03}
WORSE_METRICS = {"recall": 0.98, "pr_auc": 0.94, "business_cost_per_1000": 90000.0, "brier": 0.04}


@pytest.fixture(autouse=True)
def _set_bucket_env(monkeypatch):
    # actif pour tous les tests du fichier : sinon upload_champion_to_gcs se désactive tout seul
    monkeypatch.setenv("MODEL_ARTIFACT_BUCKET", "fake-bucket")


def test_first_upload_with_no_existing_champion_sets_the_pointer(tmp_path, monkeypatch):
    # premier modèle publié -> il devient champion, il n'y a rien à comparer
    store: dict = {}
    _install_fake_gcs(monkeypatch, store)
    model_path, metadata_path = _write_model_files(tmp_path, GOOD_METRICS, "v1")

    result = upload_champion_to_gcs(model_path, metadata_path)

    assert result["status"] == "uploaded"
    assert result["global_champion_updated"] is True
    assert json.loads(store["models/champion.json"])["model_version"] == "v1"


def test_worse_candidate_never_overwrites_a_better_gcs_champion(tmp_path, monkeypatch):
    # bug vu en prod : un run moins bon que le champion existant ne doit pas l'écraser
    store: dict = {}
    _install_fake_gcs(monkeypatch, store)

    good_model_path, good_metadata_path = _write_model_files(tmp_path / "good", GOOD_METRICS, "v-good")
    upload_champion_to_gcs(good_model_path, good_metadata_path)
    assert json.loads(store["models/champion.json"])["model_version"] == "v-good"

    worse_model_path, worse_metadata_path = _write_model_files(tmp_path / "worse", WORSE_METRICS, "v-worse")
    result = upload_champion_to_gcs(worse_model_path, worse_metadata_path)

    assert result["status"] == "uploaded"
    assert result["global_champion_updated"] is False
    # l'artefact est quand même publié (pour l'historique), mais le pointeur ne bouge pas
    assert "models/v-worse/model.joblib" in store
    assert json.loads(store["models/champion.json"])["model_version"] == "v-good"


def test_better_candidate_does_overwrite_the_gcs_champion(tmp_path, monkeypatch):
    # cas normal : un meilleur modèle doit bien remplacer le champion
    store: dict = {}
    _install_fake_gcs(monkeypatch, store)

    worse_model_path, worse_metadata_path = _write_model_files(tmp_path / "worse", WORSE_METRICS, "v-worse")
    upload_champion_to_gcs(worse_model_path, worse_metadata_path)

    good_model_path, good_metadata_path = _write_model_files(tmp_path / "good", GOOD_METRICS, "v-good")
    result = upload_champion_to_gcs(good_model_path, good_metadata_path)

    assert result["global_champion_updated"] is True
    assert json.loads(store["models/champion.json"])["model_version"] == "v-good"
