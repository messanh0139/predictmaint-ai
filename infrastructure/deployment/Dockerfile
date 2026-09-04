FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app
COPY pipelines/3_inference_ihm/api/requirements-api.txt ./requirements-api.txt
COPY constraints-model.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt -c constraints-model.txt

COPY pipelines/3_inference_ihm/api ./api
COPY src ./src
COPY storage/raw ./storage/raw
COPY storage/models/model.joblib ./storage/models/model.joblib
COPY storage/models/model_metadata.json ./storage/models/model_metadata.json

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/storage/processed /app/storage/models/candidates /app/storage/production /app/storage/reference \
    && chown -R appuser:appuser /app
USER 10001

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/live', timeout=3)" || exit 1

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
