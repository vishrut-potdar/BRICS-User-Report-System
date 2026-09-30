# Cloud Run image for the backend API. Build context is the repo root:
#   gcloud run deploy civic-api --source . --region asia-south1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/srv/data
WORKDIR /srv

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app backend/app
COPY data/packs data/packs
COPY data/reference data/reference
COPY data/processed data/processed
COPY data/synthetic data/synthetic
COPY frontend/index.html frontend/index.html

WORKDIR /srv/backend
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
