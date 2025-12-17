# Changelog

Alle relevanten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format orientiert sich an *Keep a Changelog* und die Versionsnummern folgen SemVer; für Python-Pakete nutzen wir die PEP-440-Schreibweise (z. B. `0.1.0rc1`).

## [0.1.0-rc.1] - 2025-12-17

### Added
- FastAPI-Webapp „Stellwerk“ mit Jinja2-UI und SVG-Zugstrecke zur Visualisierung von Arbeitspaketen.
- Persistenz per SQLAlchemy: Dev mit SQLite, Preprod/Prod mit Postgres.
- Planer: OpenAI-kompatible Chat-Completions optional, deterministische Heuristik als Fallback.
- Arbeitspaket-Details (Ansehen/Bearbeiten) inkl. Status, Länge und Steigung.
- In-App Debug-Konsole (Snapshot + SSE Stream) inkl. Request/Planner-Tracing.
- Docker/Compose-Deployments für Preprod/Prod sowie Dev-Startscript.

[0.1.0-rc.1]: https://github.com/NoMadAndy/goals/releases/tag/v0.1.0-rc.1
