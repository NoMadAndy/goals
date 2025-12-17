# Stellwerk

KI-gestütztes Tool, um Ziele zu setzen, Aufgaben zu definieren und diese in Arbeitspakete zu zerlegen – visualisiert als Zugstrecke mit Lok und Waggons.

## Features (MVP)

- Ziele anlegen (Dev: SQLite, Preprod/Prod: Postgres)
- KI/Heuristik plant: Zielbeschreibung + Aufgaben + Arbeitspakete
- Zugstrecke (SVG) zeigt **Länge** (Aufwand) und **Steigung** (Schwierigkeit)
- Responsive UI: Desktop ausführlich, Mobil nur das Nötigste

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e ".[dev]"
```

## Starten

```bash
./scripts/dev.sh
```

Dann öffnen: http://127.0.0.1:8000

## Tests

```bash
pytest
```

## Preprod Deployment

Siehe [docs/deployment.md](docs/deployment.md) und `scripts/deploy-preprod.sh`.

## Konfiguration

Optional über `.env` (siehe `.env.example`):

- `DATABASE_URL` (Default: `sqlite+pysqlite:///./data/stellwerk.db`)
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`

Ohne `OPENAI_API_KEY` nutzt Stellwerk automatisch einen deterministischen Heuristik-Planer.