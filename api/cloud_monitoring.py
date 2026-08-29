"""Exporte les métriques déjà collectées par prometheus_client vers Cloud Monitoring.

Ne remplace pas `/metrics` (toujours utile pour l'inspection directe et pour
Prometheus en local) : lit les mêmes objets Counter/Gauge/Histogram déjà mis à jour
par les points d'appel existants, sans y toucher, pour éviter tout risque de
désynchronisation entre les deux exports.

Se désactive silencieusement si aucune credential GCP n'est disponible (dev local),
comme le fait déjà `PREDICTION_BUCKET` pour Cloud Storage ailleurs dans ce projet.
"""
from __future__ import annotations

import logging
import time
from typing import Iterable

import google.auth
from google.api import metric_pb2, monitored_resource_pb2
from google.cloud import monitoring_v3

logger = logging.getLogger("predictmaint.cloud_monitoring")

METRIC_PREFIX = "custom.googleapis.com/predictmaint/"
NAMESPACE = "predictmaint"
JOB = "api"
TASK_ID = "api"

_client: monitoring_v3.MetricServiceClient | None = None
_project_id: str | None = None
_disabled = False
_last_latency_count = 0.0
_last_latency_sum = 0.0


def _get_client() -> monitoring_v3.MetricServiceClient | None:
    global _client, _project_id, _disabled
    if _disabled:
        return None
    if _client is not None:
        return _client
    try:
        credentials, project_id = google.auth.default()
        if not project_id:
            raise RuntimeError("aucun projet GCP détecté")
        _client = monitoring_v3.MetricServiceClient(credentials=credentials)
        _project_id = project_id
        return _client
    except Exception as exc:
        logger.warning("Export Cloud Monitoring désactivé (pas de credentials GCP) : %s", exc)
        _disabled = True
        return None


def _resource(project_id: str, region: str) -> monitored_resource_pb2.MonitoredResource:
    return monitored_resource_pb2.MonitoredResource(
        type="generic_task",
        labels={
            "project_id": project_id,
            "location": region or "global",
            "namespace": NAMESPACE,
            "job": JOB,
            "task_id": TASK_ID,
        },
    )


def _samples(metric_object, suffix: str = "") -> Iterable:
    for family in metric_object.collect():
        for sample in family.samples:
            if sample.name.endswith(suffix) and not sample.name.endswith("_created"):
                yield sample


def _gauge_series(resource, metric_type: str, labels: dict, value: float, now: float) -> monitoring_v3.TimeSeries:
    ts = monitoring_v3.TimeSeries()
    ts.metric.type = METRIC_PREFIX + metric_type
    for key, val in labels.items():
        ts.metric.labels[key] = val
    ts.resource = resource
    ts.metric_kind = metric_pb2.MetricDescriptor.MetricKind.GAUGE
    ts.value_type = metric_pb2.MetricDescriptor.ValueType.DOUBLE
    point = monitoring_v3.Point()
    point.interval.end_time = {"seconds": int(now)}
    point.value.double_value = float(value)
    ts.points = [point]
    return ts


def _counter_series(resource, metric_type: str, labels: dict, value: float, now: float) -> monitoring_v3.TimeSeries:
    """Compteur exporté en GAUGE (valeur courante à l'instant du flush), pas en
    CUMULATIVE : sur Cloud Run (scale-to-zero), chaque nouvelle instance repart avec
    un `_start_time` de processus différent, alors que resource.labels.task_id reste
    fixe — Cloud Monitoring exige un start_time stable pour une série CUMULATIVE une
    fois établie, et rejette silencieusement (côté validation serveur, sans exception
    Python) toute instance suivante qui ne le respecte pas. GAUGE n'a pas cette
    contrainte et convient mieux à du compute éphémère.
    """
    ts = monitoring_v3.TimeSeries()
    ts.metric.type = METRIC_PREFIX + metric_type
    for key, val in labels.items():
        ts.metric.labels[key] = val
    ts.resource = resource
    ts.metric_kind = metric_pb2.MetricDescriptor.MetricKind.GAUGE
    ts.value_type = metric_pb2.MetricDescriptor.ValueType.INT64
    point = monitoring_v3.Point()
    point.interval.end_time = {"seconds": int(now)}
    point.value.int64_value = int(value)
    ts.points = [point]
    return ts


def build_time_series(
    project_id: str,
    region: str,
    *,
    predictions,
    telemetry_errors,
    model_ready,
    drift_share,
    drift_psi,
    latency,
) -> list[monitoring_v3.TimeSeries]:
    """Construit les TimeSeries à envoyer, sans dépendance réseau (testable isolément)."""
    global _last_latency_count, _last_latency_sum

    now = time.time()
    resource = _resource(project_id, region)
    series: list[monitoring_v3.TimeSeries] = []

    for sample in _samples(predictions, "_total"):
        series.append(_counter_series(resource, "predictions_total", sample.labels, sample.value, now))

    for sample in _samples(telemetry_errors, "_total"):
        series.append(_counter_series(resource, "telemetry_errors_total", sample.labels, sample.value, now))

    for sample in _samples(model_ready):
        series.append(_gauge_series(resource, "model_ready", {}, sample.value, now))

    for sample in _samples(drift_share):
        series.append(_gauge_series(resource, "drift_share", {}, sample.value, now))

    for sample in _samples(drift_psi):
        series.append(_gauge_series(resource, "drift_psi", sample.labels, sample.value, now))

    # La latence est un histogramme cumulatif depuis le démarrage du process ; on publie
    # la moyenne observée sur la fenêtre écoulée depuis le dernier envoi (delta count/sum),
    # plus simple et plus robuste qu'une reconstruction de Distribution bucket par bucket.
    latency_count = next(iter(_samples(latency, "_count")), None)
    latency_sum = next(iter(_samples(latency, "_sum")), None)
    if latency_count is not None and latency_sum is not None:
        delta_count = latency_count.value - _last_latency_count
        delta_sum = latency_sum.value - _last_latency_sum
        if delta_count > 0:
            series.append(
                _gauge_series(resource, "prediction_latency_seconds_mean", {}, delta_sum / delta_count, now)
            )
        _last_latency_count = latency_count.value
        _last_latency_sum = latency_sum.value

    return series


def flush(
    region: str,
    *,
    predictions,
    telemetry_errors,
    model_ready,
    drift_share,
    drift_psi,
    latency,
) -> None:
    client = _get_client()
    if client is None:
        return
    series = build_time_series(
        _project_id,
        region,
        predictions=predictions,
        telemetry_errors=telemetry_errors,
        model_ready=model_ready,
        drift_share=drift_share,
        drift_psi=drift_psi,
        latency=latency,
    )
    if not series:
        return
    try:
        client.create_time_series(name=f"projects/{_project_id}", time_series=series)
    except Exception:
        logger.exception("échec de l'envoi des métriques à Cloud Monitoring")
