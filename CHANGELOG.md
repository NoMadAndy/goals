# Changelog

Alle relevanten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format orientiert sich an *Keep a Changelog* und die Versionsnummern folgen SemVer; für Python-Pakete nutzen wir die PEP-440-Schreibweise (z. B. `0.1.0rc1`).

## [0.1.0-rc.1] - 2025-12-17

## [Unreleased]

### Changed
- Default-Port für den Webserver ist jetzt `8002` (statt `8000`).

### Added
- Optionales `stellwerk.toml` zur Server-Konfiguration (Host/Port/Reload).

### Added
- Live-Status während der KI-Planung via Toasts (Zwischenstände statt nur Lade-Indikator).

### Added
- FastAPI-Webapp „Stellwerk“ mit Jinja2-UI und SVG-Zugstrecke zur Visualisierung von Arbeitspaketen.
- Persistenz per SQLAlchemy: Dev mit SQLite, Preprod/Prod mit Postgres.
- Planer: OpenAI-kompatible Chat-Completions optional, deterministische Heuristik als Fallback.
- Arbeitspaket-Details (Ansehen/Bearbeiten) inkl. Status, Länge und Steigung.
- In-App Debug-Konsole (Snapshot + SSE Stream) inkl. Request/Planner-Tracing.
- Docker/Compose-Deployments für Preprod/Prod sowie Dev-Startscript.

## [0.1.0-rc.2] - 2025-12-17

### Added
- Verzweigte Planung: 2–3 alternative Routen pro Ziel mit eigener Aufgaben-/Arbeitspaketstruktur.
- „Weiche stellen“-Entscheidung, um eine Route aktiv auszuwählen.
- Editierbare Begleiter/Helfer (Personen) direkt auf der Zielseite.
- Mehrspurige SVG-Strecke mit Weichen-Visualisierung und aktiver Route.

### Changed
- Heuristik-Planer erstellt deutlich granularere Pläne (mehr Aufgaben und Arbeitspakete, abhängig von Eingabe).

## [0.1.0-rc.3] - 2025-12-17

### Added
- Persistenz: Routen speichern jetzt `phase`/`kind` und Entscheidungen speichern `phase` (Grundlage für mehrere Weichen mit Merge).
- UI: Planfehler werden explizit angezeigt (kein stiller Fallback).
- Visualisierung: Strecke als Liniengraph (ohne Lok/Waggons), Fortschritt über erledigte Arbeitspakete.

### Changed
- Planer ist jetzt OpenAI-only: Ohne `OPENAI_API_KEY` werden keine Pläne mehr erzeugt.

[0.1.0-rc.3]: https://github.com/NoMadAndy/goals/releases/tag/v0.1.0-rc.3

[0.1.0-rc.2]: https://github.com/NoMadAndy/goals/releases/tag/v0.1.0-rc.2

[0.1.0-rc.1]: https://github.com/NoMadAndy/goals/releases/tag/v0.1.0-rc.1
