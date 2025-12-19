# Stellwerk (Preprod/Prod) Container
# - FastAPI via Uvicorn
# - Persistenz via Volume (STELLWERK_DATA_PATH)

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (minimal)
RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Install
COPY pyproject.toml README.md /app/
COPY src /app/src

RUN python -m pip install -U pip \
  && pip install --no-cache-dir -e .

# Database URL is provided via environment (docker-compose)
ENV DATABASE_URL=

EXPOSE 8002

CMD ["uvicorn", "stellwerk.app:app", "--host", "0.0.0.0", "--port", "8002"]
