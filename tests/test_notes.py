from stellwerk.notes import parse_work_package_notes


def test_parse_work_package_notes_extracts_sections():
    notes = """
Kurz & knapp: Das ist der Kontext.

## Schritte
1. Repo öffnen
2. Änderung durchführen
- Tests laufen lassen

## Definition of Done
- [ ] Tests sind grün
- [x] Code ist formatiert

## Risiken
- Scope creep

## Quellen
- https://example.com/docs
- https://example.com/guide)

## Bilder
https://example.com/img.png
""".strip()

    parsed = parse_work_package_notes(notes)

    assert "Kontext" in parsed.summary
    assert parsed.steps[:2] == ["Repo öffnen", "Änderung durchführen"]
    assert any(i["text"] == "Tests sind grün" for i in parsed.checklist)
    assert any(i["done"] is True for i in parsed.checklist)
    assert parsed.risks == ["Scope creep"]
    assert parsed.sources == ["https://example.com/docs", "https://example.com/guide"]
    assert parsed.images == ["https://example.com/img.png"]
