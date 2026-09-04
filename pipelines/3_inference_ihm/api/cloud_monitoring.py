# Export des métriques Prometheus vers Cloud Monitoring
from __future__ import annotations

import logging
import time
from typing import Iterable

import google.auth
from google.api import metric_pb2 as metric_types
from google.api import monitored_resource_pb2 as resource_types
from google.cloud import monitoring_v3 as monitoring

logger = logging.getLogger("predictmaint.cloud_monitoring")

METRIC_PREFIX = "custom.googleapis.com/predictmaint/"
NAMESPACE = "predictmaint"
JOB = "api"
TASK_ID = "api"

_client: monitoring.MetricServiceClient | None = None
_project_id: str | None = None
_disabled = False
_last_latency_count = 0.0
_last_latency_sum = 0.0


def _get_client() -> monitoring.MetricServiceClient | None:
    # Retourner le client Cloud Monitoring ou None si pas de credentials
    global _client, _project_id, _disabled
    if _disabled:
        return None
    if _client is not None:
        return _client
    try:
        credentials, project_id = google.auth.default()
        if not project_id:
            raise RuntimeError("aucun projet GCP détecté")
        _client = monitoring.MetricServiceClient(credentials=credentials)
        _project_id = project_id
        return _client
    except Exception as exc:
        logger.warning("Export Cloud Monitoring désactivé (pas de credentials GCP) : %s", exc)
        _disabled = True
        return None


def _resource(project_id: str, region: str) -> resource_types.MonitoredResource:
    # Construire la ressource surveillée
    return resource_types.MonitoredResource(
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
    # Itérer les échantillons Prometheus
    for family in metric_object.collect():
        for sample in family.samples:
            if sample.name.endswith(suffix) and not sample.name.endswith("_created"):
                yield sample


def _gauge_series(resource, metric_type: str, labels: dict, value: float, now: float) -> monitoring.TimeSeries:
    # Construire une série de type GAUGE
    ts = monitoring.TimeSeries()
    ts.metric.type = METRIC_PREFIX + metric_type
    for key, val in labels.items():
        ts.metric.labels[key] = val
    ts.resource = resource
    ts.metric_kind = metric_types.MetricDescriptor.MetricKind.GAUGE
    ts.value_type = metric_types.MetricDescriptor.ValueType.DOUBLE
    point = monitoring.Point()
    point.interval.end_time = {"seconds": int(now)}
    point.value.double_value = float(value)
    ts.points = [point]
    return ts


def _counter_series(resource, metric_type: str, labels: dict, value: float, now: float) -> monitoring.TimeSeries:
    # Construire une série de type compteur
    ts = monitoring.TimeSeries()
    ts.metric.type = METRIC_PREFIX + metric_type
    for key, val in labels.items():
        ts.metric.labels[key] = val
    ts.resource = resource
    ts.metric_kind = metric_types.MetricDescriptor.MetricKind.GAUGE
    ts.value_type = metric_types.MetricDescriptor.ValueType.INT64
    point = monitoring.Point()
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
) -> list[monitoring.TimeSeries]:
    # Construire les séries temporelles à envoyer
    global _last_latency_count, _last_latency_sum

    now = time.time()
    resource = _resource(project_id, region)
    series: list[monitoring.TimeSeries] = []

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

    # Calculer la latence moyenne depuis le dernier envoi
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
    # Envoyer les métriques à Cloud Monitoring
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
        # Incrémenter le compteur d'erreurs Prometheus si disponible
        try:
            # Import dynamique pour éviter dépendance circulaire
            import sys
            if 'pipelines.3_inference_ihm.api.main' in sys.modules:
                main_module = sys.modules['pipelines.3_inference_ihm.api.main']
                if hasattr(main_module, 'CLOUD_MONITORING_EXPORT_ERRORS'):
                    main_module.CLOUD_MONITORING_EXPORT_ERRORS.inc()
        except Exception:
            pass  # Ignoré si le compteur n'est pas accessible
        logger.exception("échec de l'envoi des métriques à Cloud Monitoring")
