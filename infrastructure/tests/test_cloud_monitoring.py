from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

import api.cloud_monitoring as cm


def _fresh_metrics():
    # Recrée un jeu de métriques Prometheus isolées (registre dédié) pour chaque test,
    # afin d'éviter toute pollution entre tests via le registre global par défaut.
    registry = CollectorRegistry()
    predictions = Counter("predictions_total", "x", ["risk"], registry=registry)
    telemetry_errors = Counter("telemetry_errors_total", "x", ["sink"], registry=registry)
    model_ready = Gauge("model_ready", "x", registry=registry)
    drift_share = Gauge("drift_share", "x", registry=registry)
    drift_psi = Gauge("drift_psi", "x", ["feature"], registry=registry)
    latency = Histogram("prediction_latency_seconds", "x", registry=registry)
    return predictions, telemetry_errors, model_ready, drift_share, drift_psi, latency


def test_build_time_series_reflects_current_metric_values(monkeypatch):
    # Vérifie que build_time_series traduit fidèlement l'état courant des métriques
    # Prometheus vers le format de séries temporelles attendu par Cloud Monitoring
    # (type de métrique, valeurs, et labels de ressource projet/région).
    monkeypatch.setattr(cm, "_last_latency_count", 0.0)
    monkeypatch.setattr(cm, "_last_latency_sum", 0.0)
    predictions, telemetry_errors, model_ready, drift_share, drift_psi, latency = _fresh_metrics()

    predictions.labels(risk="HIGH").inc(3)
    predictions.labels(risk="LOW").inc(5)
    telemetry_errors.labels(sink="local").inc(1)
    model_ready.set(1)
    drift_share.set(0.3)
    drift_psi.labels(feature="sensor_2").set(0.25)
    latency.observe(0.1)
    latency.observe(0.3)

    series = cm.build_time_series(
        "my-project",
        "europe-west1",
        predictions=predictions,
        telemetry_errors=telemetry_errors,
        model_ready=model_ready,
        drift_share=drift_share,
        drift_psi=drift_psi,
        latency=latency,
    )

    by_type = {s.metric.type.rsplit("/", 1)[-1]: s for s in series}
    assert set(by_type) == {
        "predictions_total",
        "telemetry_errors_total",
        "model_ready",
        "drift_share",
        "drift_psi",
        "prediction_latency_seconds_mean",
    }
    assert by_type["model_ready"].points[0].value.double_value == 1.0
    assert by_type["drift_share"].points[0].value.double_value == 0.3
    # Latence moyenne = somme des observations (0.1 + 0.3) / nombre d'observations (2) = 0.2.
    assert by_type["prediction_latency_seconds_mean"].points[0].value.double_value == 0.2
    assert by_type["drift_psi"].resource.labels["project_id"] == "my-project"
    assert by_type["drift_psi"].resource.labels["location"] == "europe-west1"


def test_build_time_series_omits_latency_when_no_new_observations(monkeypatch):
    # La latence est calculée en delta (nouvelles observations depuis le dernier flush) :
    # si aucun nouvel appel n'a eu lieu entre deux flushs, elle ne doit pas être renvoyée
    # (pour éviter de republier une valeur obsolète ou une division par zéro).
    monkeypatch.setattr(cm, "_last_latency_count", 0.0)
    monkeypatch.setattr(cm, "_last_latency_sum", 0.0)
    predictions, telemetry_errors, model_ready, drift_share, drift_psi, latency = _fresh_metrics()
    latency.observe(0.5)

    cm.build_time_series(
        "my-project",
        "europe-west1",
        predictions=predictions,
        telemetry_errors=telemetry_errors,
        model_ready=model_ready,
        drift_share=drift_share,
        drift_psi=drift_psi,
        latency=latency,
    )
    # deuxième appel sans nouvelle observation : le delta count est nul, aucun point latence
    series = cm.build_time_series(
        "my-project",
        "europe-west1",
        predictions=predictions,
        telemetry_errors=telemetry_errors,
        model_ready=model_ready,
        drift_share=drift_share,
        drift_psi=drift_psi,
        latency=latency,
    )
    types = {s.metric.type.rsplit("/", 1)[-1] for s in series}
    assert "prediction_latency_seconds_mean" not in types


def test_flush_is_a_no_op_without_gcp_credentials(monkeypatch):
    # En environnement local/CI sans Application Default Credentials GCP, flush()
    # doit se désactiver silencieusement (pas d'exception) plutôt que de faire
    # planter l'application faute de pouvoir joindre Cloud Monitoring.
    monkeypatch.setattr(cm, "_disabled", False)
    monkeypatch.setattr(cm, "_client", None)

    def _raise_default():
        # Simule l'absence de credentials GCP (comportement de google.auth.default()).
        raise OSError("no ADC available")

    monkeypatch.setattr(cm.google.auth, "default", _raise_default)
    predictions, telemetry_errors, model_ready, drift_share, drift_psi, latency = _fresh_metrics()

    # ne doit pas lever, même sans credentials GCP disponibles (cas dev local/CI)
    cm.flush(
        "europe-west1",
        predictions=predictions,
        telemetry_errors=telemetry_errors,
        model_ready=model_ready,
        drift_share=drift_share,
        drift_psi=drift_psi,
        latency=latency,
    )
    assert cm._disabled is True
