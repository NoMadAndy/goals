from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any

import httpx

from stellwerk.debug import debug_log
from stellwerk.models import Goal, Task, WorkPackage
from stellwerk.settings import settings


@dataclass(frozen=True)
class PlanRequest:
    raw_goal: str
    context: str = ""


@dataclass(frozen=True)
class PlanResult:
    goal: Goal
    source: str  # "openai" | "heuristic"
    error: str | None = None


def _seed_from_text(text: str) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def heuristic_plan(req: PlanRequest) -> Goal:
    """Deterministischer, lokaler Planer: liefert stabile Pläne für gleiche Eingaben."""

    rng = random.Random(_seed_from_text(req.raw_goal + "\n" + req.context))

    title = req.raw_goal.strip().rstrip(".")
    if not title:
        title = "Ein Ziel, das sich lohnt"

    # Einfache SMART-Umformulierung (ohne zu behaupten, es sei "perfekt")
    smart = (
        f"{title} – so konkret wie möglich, messbar über kleine Etappen, "
        "realistisch in deinem Alltag und mit einem klaren Zeitfenster."
    )

    prologue = (
        "Du stellst nicht eine große Weiche, sondern viele kleine. "
        "Jede Etappe zählt – auch wenn sie manchmal anders endet als geplant."
    )
    rallying = "Heute reicht ein guter Schritt. Der Rest rollt danach."

    # 3–5 Aufgaben
    task_count = rng.randint(3, 5)
    task_templates = [
        "Zielbild schärfen",
        "Ressourcen & Zeitfenster klären",
        "Ersten Prototyp/Entwurf bauen",
        "Feedback holen & Kurs justieren",
        "Ausrollen & Routine etablieren",
        "Reflexion & nächste Weiche",
    ]
    rng.shuffle(task_templates)

    # Konkrete Arbeitspakete pro Aufgabe (kurz, aber handlungsfähig).
    # Notes enthalten bewusst eine kleine, klare Tätigkeitsliste + DoD.
    concrete: dict[str, list[tuple[str, str, tuple[int, int], tuple[int, int]]]] = {
        "Zielbild schärfen": [
            (
                "Ergebnis beschreiben",
                "Tätigkeiten:\n- Schreibe 1–2 Sätze: Was ist am Ende anders?\n- Definiere ein sichtbares Artefakt (Dokument, Feature, Gewohnheit).\n- Notiere 1 Messkriterium (z. B. Anzahl/Woche).\n\nDefinition of Done:\n- Ein Satz Zielbild + 1 Messkriterium sind dokumentiert.",
                (1, 2),
                (2, 4),
            ),
            (
                "Randbedingungen sammeln",
                "Tätigkeiten:\n- Liste Constraints (Zeit, Budget, Tools, Menschen).\n- Entscheide: Was gehört NICHT dazu?\n- Lege einen frühesten Start + spätesten Endtermin fest.\n\nDefinition of Done:\n- 3 Constraints + 3 Nicht-Ziele sind klar.",
                (1, 3),
                (3, 5),
            ),
        ],
        "Ressourcen & Zeitfenster klären": [
            (
                "Zeitfenster blocken",
                "Tätigkeiten:\n- Finde 2–3 feste Slots im Kalender.\n- Lege die minimale Wochen-Dosis fest.\n- Entscheide eine Abbruchregel (wann ist es zu viel?).\n\nDefinition of Done:\n- 2 Slots sind im Kalender; Minimal-Dosis ist notiert.",
                (1, 2),
                (2, 4),
            ),
            (
                "Ressourcenliste erstellen",
                "Tätigkeiten:\n- Welche Tools/Materialien brauchst du?\n- Welche Person hilft bei Feedback/Review?\n- Was fehlt noch, um starten zu können?\n\nDefinition of Done:\n- Liste ist vollständig; ein nächster Beschaffungsschritt steht fest.",
                (1, 3),
                (3, 5),
            ),
        ],
        "Ersten Prototyp/Entwurf bauen": [
            (
                "Minimalumfang festlegen",
                "Tätigkeiten:\n- Definiere das kleinste vorzeigbare Ergebnis (MVP).\n- Splitte in 2–3 Teilstücke, die jeweils allein funktionieren.\n- Lege eine harte Timebox fest.\n\nDefinition of Done:\n- MVP-Satz + 2–3 Teilstücke + Timebox sind notiert.",
                (1, 2),
                (4, 6),
            ),
            (
                "Prototyp umsetzen",
                "Tätigkeiten:\n- Baue zuerst die 'Happy Path' Version.\n- Dokumentiere Stolpersteine als kurze Notizen.\n- Halte den Scope: kein Polieren, nur Funktion.\n\nDefinition of Done:\n- Prototyp läuft/demonstrierbar; 3 Notizen zu Learnings sind festgehalten.",
                (2, 5),
                (5, 8),
            ),
            (
                "Mini-Demo vorbereiten",
                "Tätigkeiten:\n- 3-Satz Story: Problem → Lösung → nächster Schritt.\n- Screenshot/kurzes Video oder Link vorbereiten.\n- 3 Fragen notieren, die du Feedbackern stellst.\n\nDefinition of Done:\n- Demo-Story + 3 Fragen sind fertig.",
                (1, 3),
                (3, 6),
            ),
        ],
        "Feedback holen & Kurs justieren": [
            (
                "Feedback einsammeln",
                "Tätigkeiten:\n- 1–3 Personen auswählen.\n- Demo zeigen und Fragen stellen.\n- Aussagen wörtlich notieren (nicht interpretieren).\n\nDefinition of Done:\n- Mind. 3 konkrete Feedbackpunkte sind dokumentiert.",
                (1, 3),
                (4, 6),
            ),
            (
                "Weiche stellen",
                "Tätigkeiten:\n- Entscheide: beibehalten / vereinfachen / umleiten.\n- Passe 1–2 Arbeitspakete an.\n- Schreibe den neuen nächsten Schritt auf.\n\nDefinition of Done:\n- Eine Entscheidung + angepasster nächster Schritt stehen fest.",
                (1, 2),
                (5, 7),
            ),
        ],
        "Ausrollen & Routine etablieren": [
            (
                "In Alltag integrieren",
                "Tätigkeiten:\n- Trigger festlegen (wann startest du?).\n- Belohnung/Abschlussritual definieren.\n- Hindernisse: 2 Gegenmaßnahmen notieren.\n\nDefinition of Done:\n- Trigger + Ritual + 2 Gegenmaßnahmen sind klar.",
                (1, 3),
                (3, 5),
            ),
            (
                "Erste Woche fahren",
                "Tätigkeiten:\n- 3 kleine Durchläufe machen (nicht perfekt).\n- Nach jedem Durchlauf 1 Satz: was ging gut?\n- Am Ende 1 Anpassung wählen.\n\nDefinition of Done:\n- 3 Durchläufe sind erledigt; 1 Anpassung ist beschlossen.",
                (2, 4),
                (4, 6),
            ),
        ],
        "Reflexion & nächste Weiche": [
            (
                "Kurz-Review",
                "Tätigkeiten:\n- 5 Minuten: Was hat Wirkung?\n- Was ist Ballast?\n- Nächste Weiche: Was wird als Nächstes wichtig?\n\nDefinition of Done:\n- 1 Erkenntnis + 1 Entscheidung sind notiert.",
                (1, 2),
                (2, 4),
            ),
        ],
    }

    tasks: list[Task] = []
    for task_title in task_templates[:task_count]:
        suggestions = list(concrete.get(task_title, []))
        rng.shuffle(suggestions)

        wp_count = rng.randint(2, 4)
        work_packages: list[WorkPackage] = []

        if suggestions:
            picked = suggestions[: min(wp_count, len(suggestions))]
            for wp_title, wp_notes, (len_min, len_max), (gr_min, gr_max) in picked:
                work_packages.append(
                    WorkPackage(
                        title=wp_title,
                        notes=wp_notes,
                        length=rng.randint(len_min, len_max),
                        grade=rng.randint(gr_min, gr_max),
                    )
                )

        # Fallback: falls eine Aufgabe mehr Pakete braucht als wir Vorschläge haben.
        while len(work_packages) < wp_count:
            i = len(work_packages) + 1
            length = rng.randint(1, 5)
            grade = rng.randint(0, 10)
            work_packages.append(
                WorkPackage(
                    title=f"{task_title}: Schritt {i}",
                    notes=(
                        "Tätigkeiten:\n- Konkreten nächsten Mini-Schritt definieren\n- Umsetzen\n- Ergebnis kurz notieren\n\n"
                        "Definition of Done:\n- Der Mini-Schritt ist erledigt und dokumentiert."
                    ),
                    length=length,
                    grade=grade,
                )
            )

        tasks.append(Task(title=task_title, work_packages=work_packages))

    return Goal(
        title=title,
        description=smart,
        tasks=tasks,
        prologue=prologue,
        rallying_cry=rallying,
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    """Extracts the first JSON object from a model response.

    Accepts raw JSON, fenced ```json blocks, or extra surrounding text.
    Raises ValueError if no JSON object can be parsed.
    """

    candidate = text.strip()
    if candidate.startswith("```"):
        # Remove code fences if present.
        candidate = candidate.strip("`")
        candidate = candidate.replace("json\n", "", 1)
        candidate = candidate.strip()

    # Try direct parse first.
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Fallback: find outermost braces.
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")

    snippet = candidate[start : end + 1]
    parsed = json.loads(snippet)
    if not isinstance(parsed, dict):
        raise ValueError("Parsed JSON is not an object")
    return parsed


async def openai_plan(req: PlanRequest) -> PlanResult:
    """OpenAI-kompatible Planung (optional). Fällt bei Fehlern auf Heuristik zurück."""

    if not settings.openai_api_key:
        await debug_log("info", "Planner: using heuristic (no OPENAI_API_KEY)")
        return PlanResult(goal=heuristic_plan(req), source="heuristic")

    prompt = (
        "Du bist ein Planungsassistent für eine App namens 'Stellwerk'.\n"
        "Formuliere aus der Nutzereingabe ein motivierendes Ziel (SMART-ish), "
        "und zerlege es in 3-5 Aufgaben und je Aufgabe 2-4 Arbeitspakete.\n"
        "Für jedes Arbeitspaket liefere: title, notes, length (1-5), grade (0-10).\n"
        "Antworte ausschließlich als JSON mit Schema: {title, description, prologue, rallying_cry, tasks:[{title, notes, work_packages:[{title, notes, length, grade}]}]}.\n\n"
        f"Eingabe: {req.raw_goal}\n"
        f"Kontext: {req.context}\n"
    )

    url = settings.openai_base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}

    payload: dict[str, Any] = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": "Antworte exakt im geforderten JSON-Format."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.6,
    }

    # If supported, ask for JSON output explicitly.
    payload["response_format"] = {"type": "json_object"}

    try:
        await debug_log(
            "info",
            "Planner: calling OpenAI-compatible endpoint",
            {"base_url": settings.openai_base_url, "model": settings.openai_model},
        )
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, headers=headers, json=payload)
            await debug_log(
                "info",
                "Planner: OpenAI response",
                {"status": resp.status_code},
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        await debug_log("info", "Planner: parsing content", {"chars": len(content or "")})
        parsed = _extract_json_object(content)

        tasks = []
        for t in parsed.get("tasks", []) or []:
            wps = []
            for wp in t.get("work_packages", []) or []:
                wps.append(
                    WorkPackage(
                        title=str(wp.get("title", "")).strip() or "Arbeitspaket",
                        notes=str(wp.get("notes", "")),
                        length=int(wp.get("length", 1)),
                        grade=int(wp.get("grade", 0)),
                    )
                )
            tasks.append(Task(title=str(t.get("title", "Aufgabe")), notes=str(t.get("notes", "")), work_packages=wps))

        goal = Goal(
            title=str(parsed.get("title", req.raw_goal)).strip() or req.raw_goal,
            description=str(parsed.get("description", "")),
            prologue=str(parsed.get("prologue", "")),
            rallying_cry=str(parsed.get("rallying_cry", "")),
            tasks=tasks,
        )
        await debug_log("info", "Planner: OpenAI plan parsed successfully", {"tasks": len(tasks)})
        return PlanResult(goal=goal, source="openai")
    except Exception as e:
        await debug_log(
            "warn",
            "Planner: OpenAI failed; falling back to heuristic",
            {"exc_type": e.__class__.__name__, "exc": str(e)[:300]},
        )
        return PlanResult(goal=heuristic_plan(req), source="heuristic", error="openai_failed")
