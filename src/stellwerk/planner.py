from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any

import httpx

from stellwerk.debug import debug_log
from stellwerk.models import Decision, DecisionOption, Goal, Person, PersonDirection, PersonRole, Route, Task, WorkPackage
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

    # Richer decomposition: 5–9 tasks depending on input length
    word_count = len((req.raw_goal or "").split())
    base_tasks = 6 if word_count >= 8 else 5
    task_count = rng.randint(base_tasks, base_tasks + 3)
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

    def build_tasks(*, bias: str) -> list[Task]:
        tasks: list[Task] = []
        for task_title in task_templates[:task_count]:
            suggestions = list(concrete.get(task_title, []))
            rng.shuffle(suggestions)

            # More WPs when goal is complex; bias can nudge the count.
            wp_min = 4 if word_count >= 8 else 3
            wp_max = 7 if word_count >= 12 else 6
            if bias == "direct":
                wp_min, wp_max = max(3, wp_min - 1), max(5, wp_max - 1)
            elif bias == "safe":
                wp_min, wp_max = wp_min, wp_max
            elif bias == "experiment":
                wp_min, wp_max = wp_min, wp_max + 1

            wp_count = rng.randint(wp_min, wp_max)
            work_packages: list[WorkPackage] = []

            if suggestions:
                picked = suggestions[: min(wp_count, len(suggestions))]
                for wp_title, wp_notes, (len_min, len_max), (gr_min, gr_max) in picked:
                    # Bias tweaks: direct slightly shorter, experiment slightly steeper.
                    length = rng.randint(len_min, len_max)
                    grade = rng.randint(gr_min, gr_max)
                    if bias == "direct":
                        length = max(1, length - 1)
                    if bias == "experiment":
                        grade = min(10, grade + 1)
                    work_packages.append(
                        WorkPackage(
                            title=wp_title,
                            notes=wp_notes,
                            length=length,
                            grade=grade,
                        )
                    )

            # Fallback: falls eine Aufgabe mehr Pakete braucht als wir Vorschläge haben.
            while len(work_packages) < wp_count:
                i = len(work_packages) + 1
                length = rng.randint(1, 6)
                grade = rng.randint(0, 10)
                if bias == "direct":
                    length = max(1, length - 1)
                if bias == "experiment":
                    grade = min(10, grade + 1)
                work_packages.append(
                    WorkPackage(
                        title=f"{task_title}: Schritt {i}",
                        notes=(
                            "Tätigkeiten:\n- Konkreten nächsten Mini-Schritt definieren\n- Umsetzen\n- Ergebnis kurz notieren\n"
                            "- Blocker/Entscheidung festhalten (falls nötig)\n\n"
                            "Definition of Done:\n- Der Mini-Schritt ist erledigt und dokumentiert."
                        ),
                        length=length,
                        grade=grade,
                    )
                )

            tasks.append(Task(title=task_title, work_packages=work_packages))
        return tasks

    # 2–3 alternative Routen
    route_count = 3 if word_count >= 10 else 2
    route_specs = [
        ("Direkt & fokussiert", "Schnell fahrbar, klare Timeboxes, wenige Umwege.", "direct"),
        ("Sicher & robust", "Risiken minimieren, Abhängigkeiten klären, saubere Absicherung.", "safe"),
        ("Experiment & Lernen", "Hypothesen testen, Feedbackschleifen, iteratives Lernen.", "experiment"),
    ]
    rng.shuffle(route_specs)
    chosen_specs = route_specs[:route_count]

    routes: list[Route] = []
    for name, desc, bias in chosen_specs:
        routes.append(Route(title=name, description=desc, tasks=build_tasks(bias=bias)))

    # Eine Weiche: Route auswählen
    decision = Decision(
        title="Weiche stellen: Welche Route passt heute?",
        prompt=(
            "Entscheide bewusst: Was ist wichtiger – Geschwindigkeit, Sicherheit oder Lernen? "
            "Du kannst die Weiche später umstellen."
        ),
        options=[DecisionOption(label=r.title, route_id=r.id) for r in routes],
    )
    decision.chosen_option_id = decision.options[0].id if decision.options else None

    return Goal(
        title=title,
        description=smart,
        routes=routes,
        decisions=[decision],
        people=[],
        active_route_id=routes[0].id if routes else None,
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
        "Ziel: Ein maximales, detailliertes Konzept als verzweigter Fahrplan.\n\n"
        "Erzeuge 2 bis 3 ALTERNATIVE Routen zum Ziel. Jede Route hat eigene Aufgaben und Arbeitspakete.\n"
        "Jede Route hat 5-9 Aufgaben. Jede Aufgabe hat 3-8 Arbeitspakete.\n"
        "Arbeitspaket-Felder: title, notes (konkrete Tätigkeiten + Definition of Done), length (1-8), grade (0-10).\n\n"
        "Erzeuge genau eine Weiche (Entscheidungsknoten), die eine Route auswählt.\n"
        "Schema (JSON):\n"
        "{\n"
        "  title, description, prologue, rallying_cry,\n"
        "  people:[{name, role:(companion|helper), direction:(with_me|ahead), notes}],\n"
        "  routes:[{title, description, tasks:[{title, notes, work_packages:[{title, notes, length, grade}]}]}],\n"
        "  decisions:[{title, prompt, options:[{label, route_index}], chosen_option_index}]\n"
        "}\n\n"
        "WICHTIG: decisions.options.route_index referenziert die Position in routes (0-basiert).\n"
        "Antworte ausschließlich als JSON-Objekt in genau diesem Schema.\n\n"
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

        # People
        people: list[Person] = []
        for p in parsed.get("people", []) or []:
            name = str(p.get("name", "")).strip()
            if not name:
                continue
            try:
                role = PersonRole(str(p.get("role", "companion")))
            except Exception:
                role = PersonRole.companion
            try:
                direction = PersonDirection(str(p.get("direction", "with_me")))
            except Exception:
                direction = PersonDirection.with_me
            people.append(Person(name=name, role=role, direction=direction, notes=str(p.get("notes", ""))))

        # Routes
        routes: list[Route] = []
        for r in parsed.get("routes", []) or []:
            tasks: list[Task] = []
            for t in r.get("tasks", []) or []:
                wps: list[WorkPackage] = []
                for wp in t.get("work_packages", []) or []:
                    wps.append(
                        WorkPackage(
                            title=str(wp.get("title", "")).strip() or "Arbeitspaket",
                            notes=str(wp.get("notes", "")),
                            length=int(wp.get("length", 1)),
                            grade=int(wp.get("grade", 0)),
                        )
                    )
                tasks.append(
                    Task(
                        title=str(t.get("title", "Aufgabe")),
                        notes=str(t.get("notes", "")),
                        work_packages=wps,
                    )
                )
            routes.append(
                Route(
                    title=str(r.get("title", "Route")).strip() or "Route",
                    description=str(r.get("description", "")),
                    tasks=tasks,
                )
            )

        # Decisions (route_index -> route_id)
        decisions: list[Decision] = []
        for d in parsed.get("decisions", []) or []:
            opts: list[DecisionOption] = []
            for opt in d.get("options", []) or []:
                label = str(opt.get("label", "Option")).strip() or "Option"
                idx = opt.get("route_index", 0)
                try:
                    idx_int = int(idx)
                except Exception:
                    idx_int = 0
                route_id = routes[idx_int].id if routes and 0 <= idx_int < len(routes) else (routes[0].id if routes else None)
                opts.append(DecisionOption(label=label, route_id=route_id))
            chosen_idx = d.get("chosen_option_index", 0)
            try:
                chosen_idx_int = int(chosen_idx)
            except Exception:
                chosen_idx_int = 0
            chosen_option_id = opts[chosen_idx_int].id if opts and 0 <= chosen_idx_int < len(opts) else (opts[0].id if opts else None)
            decisions.append(
                Decision(
                    title=str(d.get("title", "Weiche")).strip() or "Weiche",
                    prompt=str(d.get("prompt", "")),
                    options=opts,
                    chosen_option_id=chosen_option_id,
                )
            )

        active_route_id = routes[0].id if routes else None
        if decisions and decisions[0].chosen_option_id:
            for opt in decisions[0].options:
                if opt.id == decisions[0].chosen_option_id and opt.route_id:
                    active_route_id = opt.route_id

        goal = Goal(
            title=str(parsed.get("title", req.raw_goal)).strip() or req.raw_goal,
            description=str(parsed.get("description", "")),
            prologue=str(parsed.get("prologue", "")),
            rallying_cry=str(parsed.get("rallying_cry", "")),
            routes=routes,
            decisions=decisions,
            people=people,
            active_route_id=active_route_id,
        )
        await debug_log(
            "info",
            "Planner: OpenAI plan parsed successfully",
            {"routes": len(routes), "decisions": len(decisions), "people": len(people)},
        )
        return PlanResult(goal=goal, source="openai")
    except Exception as e:
        await debug_log(
            "warn",
            "Planner: OpenAI failed; falling back to heuristic",
            {"exc_type": e.__class__.__name__, "exc": str(e)[:300]},
        )
        return PlanResult(goal=heuristic_plan(req), source="heuristic", error="openai_failed")
