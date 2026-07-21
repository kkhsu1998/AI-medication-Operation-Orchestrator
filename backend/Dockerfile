# MedOps backend — FastAPI + scikit-learn/XGBoost forecasting.
FROM python:3.11-slim

# libgomp1: OpenMP runtime required by xgboost's native library.
# curl: used by the compose healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so source edits don't bust the layer cache.
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
        "fastapi>=0.110" "uvicorn[standard]>=0.29" "pydantic>=2.6" \
        "numpy>=1.24" "pandas>=2.0" "scikit-learn>=1.2" "xgboost>=2.0" \
        "sqlalchemy>=2.0" "psycopg2-binary>=2.9"

COPY app ./app

EXPOSE 8000

# Tables are created (and synthetic data seeded when empty) on startup.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
