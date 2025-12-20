# Stellwerk

KI-gestütztes Tool, um Ziele zu setzen, Aufgaben zu definieren und diese in Arbeitspakete zu zerlegen – visualisiert als Liniengraph mit Abschnitten und Abzweigen.

## Features (MVP)

- Ziele anlegen (Dev: SQLite, Preprod/Prod: Postgres)
- KI plant: Zielbeschreibung + Aufgaben + Arbeitspakete
- Liniengraph (SVG) zeigt Abschnitte/Abzweige und Fortschritt über erledigte Arbeitspakete
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
Dann öffnen: http://127.0.0.1:8002

## Server-Konfiguration (TOML)

Optional kannst du Server-Settings über eine TOML-Datei konfigurieren.

- Standardpfad: `./stellwerk.toml` (wenn vorhanden)
- Alternativ: `stellwerk --config pfad/zur/datei.toml`

`./scripts/dev.sh` berücksichtigt optional `STELLWERK_CONFIG` (Pfad zur TOML-Datei).

Beispiel: siehe `stellwerk.example.toml`.

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
- optional: `OPENAI_TIMEOUT_SECONDS`, `OPENAI_RETRIES`

Ohne `OPENAI_API_KEY` kann Stellwerk keine Pläne erstellen (es gibt keinen Heuristik-Fallback).

## 📚 Projekt Enhancement Dokumentation

Umfassende Dokumentation zur Verbesserung des Projekts mit besserer Organisation und intelligenterer KI-Logik:

**[→ Zur Dokumentation (DOKUMENTATION_INDEX.md)](./DOKUMENTATION_INDEX.md)** - Start hier!

Die Dokumentation enthält:
- ✅ Umfassender Prompt für Stellwerk 2.0 (34 KB)
- ✅ Inkrementeller Refactoring-Guide (29 KB)
- ✅ Architektur-Diagramme und Vergleiche
- ✅ Entscheidungshilfe: Refactoring vs. Neuaufbau vs. Hybrid
- ✅ 12-Wochen Implementierungs-Roadmap
- ✅ Konkrete Code-Beispiele und Best Practices