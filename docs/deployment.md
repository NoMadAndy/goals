# Deployment

Dieses Repository macht **keine Annahmen** über Cloud/Provider. Stattdessen gibt es ein reproduzierbares Preprod-Deployment via Docker Compose.

## Persistenz-Strategie

- **Dev**: SQLite (Datei) via `DATABASE_URL=sqlite+pysqlite:///./data/stellwerk.db`
- **Preprod/Prod**: Postgres (Container) via Docker Compose (DB startet mit)

## Preprod (Docker Compose)

### Voraussetzungen


Wichtig: Für den pull-basierten Ansatz muss der Repo-Pfad (z. B. `/opt/goals`) ein echtes Git-Checkout sein (also mit `.git/`). Ein reines Kopieren der Dateien ohne Git-Metadaten reicht nicht.
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

### Auto-Deploy (Preprod-Host pullt regelmäßig)

Statt GitHub Actions kann auf dem Preprod-Host ein `systemd` Timer laufen, der regelmäßig auf neue Commits prüft und dann deployt.

Im Repo sind dafür enthalten:

- `scripts/preprod-autodeploy.sh` (prüft `origin/main` und ruft bei Änderungen `scripts/deploy-preprod.sh --update` auf)
- `scripts/systemd/stellwerk-preprod-autodeploy.service`
- `scripts/systemd/stellwerk-preprod-autodeploy.timer`

Setup auf dem Preprod-Host (Beispiel):

```bash
cd /opt/goals
chmod +x scripts/preprod-autodeploy.sh

sudo cp scripts/systemd/stellwerk-preprod-autodeploy.service /etc/systemd/system/
sudo cp scripts/systemd/stellwerk-preprod-autodeploy.timer /etc/systemd/system/

# Repo-Pfad konfigurieren (empfohlen)
sudo tee /etc/stellwerk-preprod-autodeploy.env >/dev/null <<'ENV'
REPO_DIR=/opt/goals
# Optional: zusätzliche Deploy-Flags, z.B. "--down" oder "--no-cache"
DEPLOY_FLAGS=
ENV

sudo systemctl daemon-reload
sudo systemctl enable --now stellwerk-preprod-autodeploy.timer
systemctl status stellwerk-preprod-autodeploy.timer
```

Logs:

```bash
journalctl -u stellwerk-preprod-autodeploy.service -n 200 --no-pager
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

Wenn du TLS/Domain willst, setze einen Reverse Proxy (z. B. Caddy/Nginx/Traefik) vor `http://127.0.0.1:8002`.
