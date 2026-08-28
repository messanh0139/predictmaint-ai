from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st


API_URL = os.getenv("API_URL", "http://api:8080").rstrip("/")
API_AUDIENCE = os.getenv("API_AUDIENCE", "").strip()
DATA_PATH = Path(os.getenv("DEMO_DATA_PATH", "/app/data/raw/test_FD001.txt"))
METADATA_PATH = Path(os.getenv("MODEL_METADATA_PATH", "/app/models/model_metadata.json"))
METRICS_PATH = Path(os.getenv("TEST_METRICS_PATH", "/app/models/test_metrics.json"))

BASE_COLUMNS = [
    "engine_id",
    "cycle",
    "setting_1",
    "setting_2",
    "setting_3",
    *[f"sensor_{index}" for index in range(1, 22)],
]
SNAPSHOT_COLUMNS = [column for column in BASE_COLUMNS if column != "engine_id"]

st.set_page_config(
    page_title="PredictMaint AI",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .stApp { background: linear-gradient(145deg, #07111f 0%, #0d1b2a 55%, #10283b 100%); }
      [data-testid="stSidebar"] { background: #081521; }
      [data-testid="stMetric"] {
        background: rgba(16, 43, 61, 0.85); border: 1px solid #1e526c;
        padding: 1rem; border-radius: 12px;
      }
      .hero {
        padding: 1.4rem 1.6rem; border: 1px solid #1e526c; border-radius: 16px;
        background: linear-gradient(110deg, rgba(12, 42, 58, .96), rgba(8, 25, 40, .96));
        margin-bottom: 1rem;
      }
      .hero h1 { margin: 0; color: #f4fbff; font-size: 2rem; }
      .hero p { margin: .35rem 0 0; color: #a9c8d8; }
      .risk-high, .risk-low {
        padding: 1.1rem; border-radius: 12px; text-align: center; font-weight: 800;
        font-size: 1.35rem; letter-spacing: .04em;
      }
      .risk-high { background: #5e1c24; color: #ffd7d7; border: 1px solid #e35d6a; }
      .risk-low { background: #123f35; color: #c9ffe9; border: 1px solid #35b88b; }
      .service-link { display: block; padding: .55rem .7rem; margin: .35rem 0;
        border-radius: 8px; color: #bde9ff !important; background: #10283b; text-decoration: none; }
      footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data
def load_demo_data(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=r"\s+", header=None, names=BASE_COLUMNS)


def api_headers() -> dict[str, str]:
    if not API_AUDIENCE:
        return {}
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token

        token = id_token.fetch_id_token(Request(), API_AUDIENCE)
        return {"Authorization": f"Bearer {token}"}
    except Exception as exc:
        raise RuntimeError(f"Impossible de créer le jeton d'identité Cloud Run: {exc}") from exc


def api_get(path: str) -> tuple[dict, str | None]:
    try:
        response = requests.get(f"{API_URL}{path}", headers=api_headers(), timeout=5)
        response.raise_for_status()
        return response.json(), None
    except (requests.RequestException, RuntimeError) as exc:
        return {}, str(exc)


def api_post(path: str, payload: dict) -> tuple[dict, str | None]:
    try:
        response = requests.post(
            f"{API_URL}{path}", json=payload, headers=api_headers(), timeout=30
        )
        response.raise_for_status()
        return response.json(), None
    except (requests.RequestException, RuntimeError) as exc:
        detail = ""
        if getattr(exc, "response", None) is not None:
            detail = f" — {exc.response.text}"
        return {}, f"{exc}{detail}"


metadata = load_json(METADATA_PATH)
test_metrics = load_json(METRICS_PATH)
health, health_error = api_get("/ready")

with st.sidebar:
    st.title("⚙️ PredictMaint")
    st.caption("Cockpit de maintenance prédictive")
    if health_error:
        st.error("API indisponible")
    else:
        st.success("API et modèle opérationnels")
        st.caption(f"Version : {health.get('model_version', 'n/a')}")

    st.divider()
    st.markdown("**Écosystème MLOps**")
    st.markdown(
        """
        <a class="service-link" href="http://localhost:9090" target="_blank">Prometheus ↗</a>
        <a class="service-link" href="http://localhost:3001" target="_blank">Grafana ↗</a>
        <a class="service-link" href="http://localhost:5000" target="_blank">MLflow ↗</a>
        <a class="service-link" href="http://localhost:8081/docs" target="_blank">Documentation API ↗</a>
        """,
        unsafe_allow_html=True,
    )
    st.divider()
    st.caption("Données de démonstration : NASA C-MAPSS FD001")

st.markdown(
    """
    <div class="hero">
      <h1>Maintenance prédictive des turbofans</h1>
      <p>Détecter un risque de défaillance dans les 30 prochains cycles et prioriser l'intervention.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

metric_columns = st.columns(4)
metric_columns[0].metric("Modèle champion", metadata.get("model_name", "—"))
metric_columns[1].metric("Recall test", f"{test_metrics.get('recall', 0):.1%}")
metric_columns[2].metric("PR-AUC test", f"{test_metrics.get('pr_auc', 0):.3f}")
metric_columns[3].metric("Fenêtre d'alerte", f"{metadata.get('failure_window', 30)} cycles")

prediction_tab, performance_tab, architecture_tab = st.tabs(
    ["🔎 Démonstration prédictive", "📊 Performance", "🔗 Parcours de présentation"]
)

with prediction_tab:
    if not DATA_PATH.exists():
        st.error(f"Jeu de démonstration absent : {DATA_PATH}")
    elif health_error:
        st.error(f"Impossible de joindre l'API : {health_error}")
    else:
        demo_data = load_demo_data(DATA_PATH)
        selector_col, cycle_col = st.columns([1, 2])
        engine_id = selector_col.selectbox(
            "Moteur NASA",
            options=demo_data["engine_id"].drop_duplicates().astype(int).tolist(),
        )
        engine_data = demo_data[demo_data["engine_id"] == engine_id].copy()
        max_cycle = int(engine_data["cycle"].max())
        selected_cycle = cycle_col.slider(
            "Dernier cycle observé",
            min_value=1,
            max_value=max_cycle,
            value=max_cycle,
            help="La prédiction n'utilise que l'historique disponible jusqu'à ce cycle.",
        )
        history = engine_data[engine_data["cycle"] <= selected_cycle]

        chart_columns = ["sensor_2", "sensor_4", "sensor_7", "sensor_11", "sensor_15"]
        st.line_chart(history.set_index("cycle")[chart_columns], height=240)

        if st.button("Analyser le risque", type="primary", use_container_width=True):
            payload = {
                "engine_id": int(engine_id),
                "history": history[SNAPSHOT_COLUMNS].to_dict(orient="records"),
            }
            result, error = api_post("/predict", payload)
            if error:
                st.error(f"La prédiction a échoué : {error}")
            else:
                st.session_state["last_prediction"] = result

        result = st.session_state.get("last_prediction")
        if result:
            probability = float(result["failure_probability"])
            risk = result["risk"]
            result_columns = st.columns([1.25, 1, 1])
            css_class = "risk-high" if risk == "HIGH" else "risk-low"
            label = "INTERVENTION À PRIORISER" if risk == "HIGH" else "SURVEILLANCE NORMALE"
            result_columns[0].markdown(
                f'<div class="{css_class}">{label}</div>', unsafe_allow_html=True
            )
            result_columns[1].metric("Probabilité de défaillance", f"{probability:.2%}")
            result_columns[2].metric("Seuil décisionnel", f"{float(result['threshold']):.3%}")
            st.progress(min(max(probability, 0.0), 1.0))
            st.caption(
                f"Prédiction `{result['prediction_id']}` · moteur {result['engine_id']} · "
                f"cycle {result['last_cycle']} · modèle {result.get('model_version', 'n/a')}"
            )

            with st.expander("Enregistrer le résultat terrain ultérieur"):
                actual_failure = st.radio(
                    "Défaillance observée dans les 30 cycles ?",
                    options=[0, 1],
                    format_func=lambda value: "Oui" if value else "Non",
                    horizontal=True,
                )
                actual_rul = st.number_input("RUL réel (optionnel)", min_value=0, value=30)
                if st.button("Envoyer le feedback"):
                    feedback_result, feedback_error = api_post(
                        "/feedback",
                        {
                            "prediction_id": result["prediction_id"],
                            "actual_failure_within_30_cycles": actual_failure,
                            "actual_rul": actual_rul,
                        },
                    )
                    if feedback_error:
                        st.error(feedback_error)
                    else:
                        st.success("Feedback enregistré pour le monitoring continu.")

with performance_tab:
    st.subheader("Résultats sur le holdout externe verrouillé")
    perf_columns = st.columns(4)
    perf_columns[0].metric("Recall", f"{test_metrics.get('recall', 0):.1%}")
    perf_columns[1].metric("Précision", f"{test_metrics.get('precision', 0):.1%}")
    perf_columns[2].metric("ROC-AUC", f"{test_metrics.get('roc_auc', 0):.3f}")
    perf_columns[3].metric("F1", f"{test_metrics.get('f1', 0):.3f}")

    confusion = pd.DataFrame(
        {
            "Cas": ["Vrais négatifs", "Faux positifs", "Faux négatifs", "Vrais positifs"],
            "Nombre": [
                test_metrics.get("tn", 0),
                test_metrics.get("fp", 0),
                test_metrics.get("fn", 0),
                test_metrics.get("tp", 0),
            ],
        }
    ).set_index("Cas")
    st.bar_chart(confusion, horizontal=True, height=280)
    st.info(
        "Le seuil a été appris sur un ensemble de calibration dédié. Le holdout NASA externe "
        "est réservé à l'évaluation finale et n'est pas utilisé pour ajuster le modèle."
    )

with architecture_tab:
    st.subheader("Scénario conseillé pour la soutenance")
    st.markdown(
        """
        1. **Streamlit** — sélectionner un moteur, faire varier le cycle et produire une alerte.
        2. **FastAPI** — montrer le contrat `/predict` et la réponse traçable.
        3. **Grafana** — vérifier le volume, la latence et l'état du modèle.
        4. **MLflow** — comparer les expériences et retrouver les artefacts versionnés.
        5. **Boucle de feedback** — rattacher la vérité terrain puis déclencher le réentraînement.
        """
    )
    st.code(
        "Capteurs → Streamlit → FastAPI → Modèle\n"
        "                         ├→ Prometheus → Grafana\n"
        "Feedback → Monitoring → Réentraînement → MLflow",
        language="text",
    )
