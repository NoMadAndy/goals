# Deployment

Dieses Repository macht **keine Annahmen** über Cloud/Provider. Stattdessen gibt es ein reproduzierbares Preprod-Deployment via Docker Compose.

## Persistenz-Strategie

- **Dev**: SQLite (Datei) via `DATABASE_URL=sqlite+pysqlite:///./data/stellwerk.db`
- **Preprod/Prod**: Postgres (Container) via Docker Compose (DB startet mit)

## Preprod (Docker Compose)

### Voraussetzungen

- Host mit `docker` und `docker compose` (Plugin)
- Port `8000` erreichbar (oder via Reverse Proxy)

### Setup

1. Repo auf dem Preprod-Host auschecken/aktualisieren
2. Optional: `.env` anlegen (siehe `.env.example`)

Wichtige Variablen:

- `POSTGRES_PASSWORD` (wird für DB und App verwendet)

Beispiel `.env` (nur wenn KI genutzt wird):

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

Persistenz:

- Standard: Docker Volume `stellwerk-db-preprod` (siehe `docker-compose.preprod.yml`)

### Deploy

Auf dem Preprod-Host:

```bash
chmod +x scripts/deploy-preprod.sh
./scripts/deploy-preprod.sh
```

## Prod (Docker Compose)

Analog zu Preprod, aber mit `docker-compose.prod.yml` und `scripts/deploy-prod.sh`.

```bash
chmod +x scripts/deploy-prod.sh
./scripts/deploy-prod.sh
```

### Rollback

Rollback ist hier bewusst simpel gehalten:

- Wenn du mit Git deployest: `git checkout <sha>` und erneut `./scripts/deploy-preprod.sh`
- Wenn du Images taggst: passe `image:` in `docker-compose.preprod.yml` an und `docker compose up -d`

## Reverse Proxy (optional)

Wenn du TLS/Domain willst, setze einen Reverse Proxy (z. B. Caddy/Nginx/Traefik) vor `http://127.0.0.1:8000`.
