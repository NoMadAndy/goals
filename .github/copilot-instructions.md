# Copilot-Anweisungen (Repository: Claim)

Diese Datei beschreibt verbindliche Leitlinien für Beiträge, die mit GitHub Copilot (oder anderen KI-Tools) erstellt werden. Ziel ist: **kleine, nachvollziehbare Änderungen**, **grüne CI**, **saubere Dokumentation** und **sofortige Merge-Fähigkeit nach `main`**.

> Geltungsbereich: Code, Tests, CI-Konfiguration, Dokumentation, Scripts und Infrastruktur im gesamten Repository.

---

## 1) Grundprinzipien

- **Keine Annahmen**: Wenn etwas unklar ist, **im Code nachsehen** oder eine **Rückfrage** stellen.
- **Repo zuerst**: Bevor du Änderungen vorschlägst, **durchsuche den Codebestand** (Struktur, Konventionen, vorhandene Utilities, Patterns).
- **Minimal, aber vollständig**: Änderungen sollten klein sein, aber das Problem **end-to-end** lösen (inkl. Tests & Doku).
- **Determinismus vor Magie**: Lieber explizite Implementierung und klare Fehlerbehandlung als implizite Side-Effects.

### Definition of Done (DoD)
- [ ] Implementierung entspricht dem gewünschten Verhalten (inkl. Edge Cases)
- [ ] Relevante Tests existieren/aktualisiert und sind grün
- [ ] Lokale Test-/Build-Schritte dokumentiert oder unverändert gültig
- [ ] Doku/Changelog (falls vorhanden) aktualisiert
- [ ] CI ist grün; keine neuen Linter-/Type-Fehler
- [ ] PR ist klein genug zum schnellen Review

---

## 2) Recherche- und Sorgfaltsanforderungen

### Codebase-Research (pflicht)
Bevor du Code schreibst/änderst:

- [ ] **Suche nach existierenden Implementierungen** (z. B. ähnliche Funktionen/Services/Komponenten)
- [ ] Prüfe vorhandene **Konventionen**: Namensgebung, Fehlerbehandlung, Logging, Dependency Injection, Architektur
- [ ] Identifiziere betroffene Stellen: Caller/Consumer, Interfaces, Konfiguration, Migrations, Doku
- [ ] Prüfe bestehende Tests und Test-Harness (Fixtures, Mocks, Test Utilities)

### Permalinks (wenn du in PR/Review/Issue referenzierst)
- Bei Diskussionen/Begründungen: **Links als GitHub-Permalinks** verwenden (auf konkrete Commit-SHAs), nicht auf floating Branches.
- Referenziere relevante Stellen:
  - [ ] Alte Logik
  - [ ] Neue Logik
  - [ ] Tests, die das Verhalten beweisen

### Vermeide Halluzinationen
- Keine erfundenen Befehle, Pfade oder Tools.
- Wenn du nicht sicher bist:
  - [ ] Repo nach `package.json`, `pyproject.toml`, `go.mod`, `pom.xml`, `Makefile`, `Dockerfile`, CI-Workflow-Dateien durchsuchen
  - [ ] Existierende `README`/`CONTRIBUTING`/`docs/` prüfen
  - [ ] Rückfrage stellen statt raten

---

## 3) Tests

> Dieser Abschnitt ist so geschrieben, dass er in **jedem** Setup funktioniert. Wo das Repo konkrete Befehle definiert, **verwende diese** (z. B. `make test`, `npm test`, `pytest`, `dotnet test`).

### 3.1 Tests ausführen (lokal)

1. **Schneller Check** (typisch):
   - [ ] Lint/Format
   - [ ] Unit Tests
   - [ ] (Optional) Typecheck/Build

2. **Vollständiger Check**:
   - [ ] Unit + Integration + E2E (falls vorhanden)
   - [ ] DB/Container-abhängige Tests (falls vorhanden)

**Anforderung:** Jede Änderung muss mit den im Repo etablierten Standardbefehlen getestet werden.

### 3.2 Tests hinzufügen

- **Neue Funktionalität ⇒ neue Tests**.
- **Bugfix ⇒ Regressionstest**, der vorher fehlschlägt und nach Fix grün ist.
- Nutze vorhandene Test-Patterns:
  - [ ] Bestehende Test-Ordner/Dateinamen
  - [ ] Vorhandene Fixtures/Factories
  - [ ] Vorhandene Mocking-Utilities

**Testarten (je nach Repo):**
- Unit: schnelle Logiktests ohne I/O
- Integration: mit echten Subsystemen (DB, Filesystem, HTTP-Mocks)
- E2E: End-to-End-Flows (UI/API)

### 3.3 Tests verifizieren (CI-Parität)

- Stelle sicher, dass lokale Befehle der CI entsprechen:
  - [ ] gleiche Node/Python/.NET/Java-Version (falls relevant)
  - [ ] gleiche Env-Variablen/Secrets-Anforderungen (in CI dokumentiert)
  - [ ] gleiche Container/Services (z. B. Postgres, Redis)

**Akzeptanzkriterium:** PR darf **nur** gemergt werden, wenn alle relevanten CI-Checks grün sind.

---

## 4) Deployment

> Deployment-Anweisungen müssen sich an den im Repo vorhandenen Pipelines orientieren (z. B. GitHub Actions, Helm, Terraform, Cloud Run, Azure, etc.). Wenn unklar, **CI-Workflows** und `docs/`/`README` analysieren.

### 4.1 Umgebungen
Definiere/verwende konsistent, falls vorhanden:
- **dev**: schnelle Iteration, feature branches
- **staging**: release candidate / produktionsnah
- **prod**: Produktion

Wenn das Repo andere Namen benutzt (z. B. `test`, `uat`), sind diese maßgeblich.

### 4.2 Deployment-Schritte (Checklist)
- [ ] Version/Tag/Release-Mechanik identifiziert (SemVer? Git tags? Releases?)
- [ ] Build-Artefakte erzeugt (Container/Image/Bundle)
- [ ] Konfiguration für Zielumgebung geprüft (Env Vars, Feature Flags)
- [ ] Datenbank-Migrationen geprüft/ausgeführt (falls relevant)
- [ ] Smoke Test / Health Check nach Deployment
- [ ] Rollback-Strategie klar (z. B. vorheriges Image/Tag)

### 4.3 Required Checks & Gates
Vor Deployment nach `staging`/`prod`:
- [ ] Alle CI-Checks grün (Tests, Lint, Build)
- [ ] Security/Dependency-Checks grün (falls vorhanden)
- [ ] Mindestens 1 Review-Approval (oder Repo-Regel) vorhanden
- [ ] Keine offenen "TODO"/"FIXME" in kritischen Pfaden ohne Ticket/Begründung

### 4.4 Dokumentation bei Deployment-Änderungen
Wenn Deploy/Infra geändert wird:
- [ ] Update in `README` oder `docs/deployment.md` (falls vorhanden)
- [ ] Neue Umgebungsvariablen dokumentieren (Name, Zweck, Beispiel)
- [ ] Migrations- und Rollback-Anleitung ergänzen

---

## 5) Dokumentation

### 5.1 Was aktualisieren?
- **README**: Setup, Quickstart, Run/Test-Befehle, Konfiguration
- **docs/** (falls vorhanden): tiefergehende Guides (Architektur, Deployment, Betrieb)
- **CHANGELOG** (falls vorhanden): Nutzerrelevante Änderungen
- **API-Doku** (OpenAPI/Swagger/GraphQL-Schema), wenn Schnittstellen geändert werden

### 5.2 Wo genau dokumentieren?
- Wenn es bereits passende Dateien gibt: **dort** erweitern, nicht neu erfinden.
- Neue Dokumente nur, wenn nötig; dann klare Einordnung:
  - `docs/testing.md` für Teststrategie
  - `docs/deployment.md` für Deployment
  - `docs/architecture.md` für Architekturentscheidungen

### 5.3 Doku-Checklist pro PR
- [ ] Setup/Run/Test-Befehle weiterhin korrekt
- [ ] Neue/änderte Konfigurationswerte beschrieben
- [ ] Öffentliche APIs/Interfaces beschrieben
- [ ] Beispiele/Code Snippets aktuell

---

## 6) Workflow: PRs, Reviews und Merge nach `main`

Ziel: Änderungen sollen **so erstellt** werden, dass ein Merge nach `main` sofort möglich ist.

### 6.1 PR-Größe und Scope
- PRs **klein halten** (idealerweise ein Thema, ein Feature/Bugfix).
- Große Refactors aufteilen:
  - [ ] Vorbereitung (mechanisch, ohne Verhalten)
  - [ ] Verhaltensänderung
  - [ ] Aufräumen/Abschlüsse

### 6.2 Branching
- Feature-Branches vom aktuellen `main`.
- Branch regelmäßig rebasen/aktualisieren, damit CI repräsentativ bleibt.

### 6.3 PR-Beschreibung (Minimum)
- [ ] Kontext/Problem
- [ ] Lösung/Approach
- [ ] Test-Nachweis (lokal + CI) inkl. Befehle
- [ ] Risiko/Impact + Rollback-Hinweis (wenn relevant)
- [ ] Doku-Änderungen verlinkt

### 6.4 Required Reviews & Qualität
- Mindestens die in Repo-Regeln geforderte Anzahl Approvals.
- Reviewer müssen die Änderung nachvollziehen können:
  - [ ] klare Commits / nachvollziehbare Diff
  - [ ] Tests decken Änderungen ab
  - [ ] keine ungenutzten Dateien/Dead Code

### 6.5 Merge-Strategie
- Bevorzugt: **Squash Merge** (ein sauberer Commit pro PR), sofern nicht anders geregelt.
- Merge nur, wenn:
  - [ ] Branch up-to-date oder bewusst toleriert
  - [ ] CI grün
  - [ ] Approvals vorhanden
  - [ ] keine Blocker-Kommentare offen

### 6.6 Post-Merge Checks
- [ ] Überprüfen, dass `main` grün bleibt
- [ ] Falls Deployment an `main` gekoppelt ist: Monitoring/Smoke Test

---

## 7) Sicherheits- und Qualitätsanforderungen

- Keine Secrets in Code/Logs/Docs.
- Neue Dependencies nur mit Begründung und (falls vorhanden) Aktualisierung von Lockfiles.
- Fehlerbehandlung:
  - [ ] verständliche Fehlermeldungen
  - [ ] keine Sensitive Data leaken

---

## 8) Copilot-spezifische Arbeitsweise

- Copilot darf beim **Boilerplate** helfen, aber du musst:
  - [ ] Code mit Repo-Konventionen abgleichen
  - [ ] Tests ergänzen
  - [ ] Änderungen erklären können (PR-Text)
- Bei Unsicherheit: zuerst Leseschritte (Search) durchführen, dann Implementation.

---

## 9) Checklisten (zum Kopieren in PRs)

### PR-Checklist
- [ ] Scope klein und verständlich
- [ ] Tests hinzugefügt/aktualisiert
- [ ] Tests lokal ausgeführt (Befehl + Ergebnis in PR)
- [ ] CI grün
- [ ] Doku aktualisiert (README/docs/CHANGELOG)
- [ ] Keine offenen Blocker-Kommentare

### Deployment-Checklist (falls relevant)
- [ ] Umgebungen/Configs geprüft
- [ ] Migrations/Rollback bedacht
- [ ] Smoke Test nach Deployment möglich/beschrieben

### Research-Checklist
- [ ] Repo nach existierender Lösung/Pattern durchsucht
- [ ] Permalinks für Code-Referenzen vorbereitet (falls diskutiert)
- [ ] Keine Annahmen über Tools/Commands ohne Nachweis
