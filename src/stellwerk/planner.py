from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass
import re
from typing import Any

import httpx

from stellwerk.debug import debug_log
from stellwerk.models import (
    Decision,
    DecisionOption,
    Goal,
    GraphEdge,
    Person,
    PersonDirection,
    PersonRole,
    Route,
    RouteKind,
    Task,
    WorkPackage,
)
from collections.abc import Callable

from stellwerk.settings import settings


def _emit_progress(
    progress_events: list[dict[str, Any]] | None,
    emit: Callable[[dict[str, Any]], None] | None,
    *,
    level: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> None:
    ev: dict[str, Any] = {"level": level, "message": message}
    if data:
        ev["data"] = data

    if progress_events is not None:
        progress_events.append(ev)
    if emit is not None:
        try:
            emit(ev)
        except Exception:
            # Best-effort only.
            pass


@dataclass(frozen=True)
class PlanRequest:
    raw_goal: str
    context: str = ""


@dataclass(frozen=True)
class PlanResult:
    goal: Goal | None
    source: str  # currently: "openai"
    error: str | None = None


@dataclass(frozen=True)
class PlanResultWithProgress:
    result: PlanResult
    progress_events: list[dict[str, Any]]


def parse_openai_plan(
    parsed: dict[str, Any],
    req: PlanRequest,
    *,
    progress_events: list[dict[str, Any]] | None = None,
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> Goal:
    """Parse a validated OpenAI JSON response into the domain model.

    Raises ValueError for invalid shapes so callers can surface explicit errors.
    """

    # People
    people: list[Person] = []
    for p in parsed.get("people", []) or []:
        if not isinstance(p, dict):
            continue
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
        people.append(
            Person(name=name, role=role, direction=direction, notes=str(p.get("notes", "")))
        )

    def parse_tasks(container: dict[str, Any], *, route_title: str = "") -> list[Task]:
        tasks: list[Task] = []

        def _coerce_int_field(
            value: Any,
            *,
            default: int,
            min_value: int,
            max_value: int,
            field_name: str,
        ) -> int:
            # Strict for numeric inputs: out-of-bounds should still fail.
            if isinstance(value, int):
                if not (min_value <= value <= max_value):
                    raise ValueError(
                        f"WorkPackage.{field_name} out of bounds ({min_value}..{max_value})"
                    )
                return value

            # Strict for numeric strings: out-of-bounds should still fail.
            if isinstance(value, str):
                s = value.strip()
                if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
                    n = int(s)
                    if not (min_value <= n <= max_value):
                        raise ValueError(
                            f"WorkPackage.{field_name} out of bounds ({min_value}..{max_value})"
                        )
                    return n

                # Tolerant for strings with units/extra text: extract first integer and clamp.
                m = re.search(r"-?\d+", s)
                if m:
                    try:
                        n = int(m.group(0))
                        return max(min_value, min(max_value, n))
                    except Exception:
                        return default

            # Anything else: fall back to default.
            return default

        for t in container.get("tasks", []) or []:
            if not isinstance(t, dict):
                continue
            task_title = str(t.get("title", "Aufgabe"))
            wps: list[WorkPackage] = []
            for wp in t.get("work_packages", []) or []:
                if not isinstance(wp, dict):
                    continue
                wp_title = str(wp.get("title", "")).strip() or "Arbeitspaket"

                length = _coerce_int_field(
                    wp.get("length", 1),
                    default=1,
                    min_value=1,
                    max_value=8,
                    field_name="length",
                )
                grade = _coerce_int_field(
                    wp.get("grade", 0),
                    default=0,
                    min_value=0,
                    max_value=10,
                    field_name="grade",
                )
                wps.append(
                    WorkPackage(
                        title=wp_title,
                        notes=str(wp.get("notes", "")),
                        length=length,
                        grade=grade,
                    )
                )

                # Progress: keep it bounded so we don't spam.
                if progress_events is None or len(progress_events) < 35:
                    _emit_progress(
                        progress_events,
                        emit,
                        level="info",
                        message=f"Fülle Arbeitspaket: {wp_title}",
                        data={"route": route_title, "task": task_title},
                    )
            tasks.append(
                Task(
                    title=task_title,
                    notes=str(t.get("notes", "")),
                    work_packages=wps,
                )
            )
        return tasks

    routes: list[Route] = []
    decisions: list[Decision] = []
    edges: list[GraphEdge] = []

    def _looks_like_graph_schema(doc: dict[str, Any]) -> bool:
        """Heuristic: graph schema uses explicit node IDs and node-attached decisions.

        We accept this even if `edges` is missing, as long as decisions reference
        routes via `from`/`to` identifiers.
        """

        raw_routes = doc.get("routes")
        if not isinstance(raw_routes, list) or not raw_routes:
            return False

        raw_decisions = doc.get("decisions")
        if not isinstance(raw_decisions, list) or not raw_decisions:
            return False

        for d in raw_decisions:
            if not isinstance(d, dict):
                continue
            if (
                d.get("from") is None
                and d.get("from_route_id") is None
                and d.get("from_route") is None
            ):
                continue
            for opt in d.get("options", []) or []:
                if not isinstance(opt, dict):
                    continue
                if (
                    opt.get("to") is not None
                    or opt.get("to_route_id") is not None
                    or opt.get("route_id") is not None
                ):
                    return True

        return False

    # New schema: graph (routes[] + edges[] + decisions[] attached to nodes)
    # Note: the model may use string IDs. We map them to domain UUIDs.
    if parsed.get("edges") is not None or _looks_like_graph_schema(parsed):
        _emit_progress(
            progress_events, emit, level="info", message="Struktur: Graph wird verarbeitet"
        )
        raw_routes = parsed.get("routes") or []
        if not isinstance(raw_routes, list) or not raw_routes:
            raise ValueError("routes must be a non-empty list")

        key_to_route: dict[str, Route] = {}
        for i, r in enumerate(raw_routes):
            if not isinstance(r, dict):
                continue
            raw_key = r.get("id") or r.get("key") or r.get("route_id") or f"r{i}"
            key = str(raw_key).strip() or f"r{i}"
            # Ensure uniqueness if the model repeats IDs.
            if key in key_to_route:
                key = f"{key}__{i}"

            try:
                kind = RouteKind(str(r.get("kind", "trunk")))
            except Exception:
                kind = RouteKind.trunk
            try:
                phase = int(r.get("phase", 0) or 0)
            except Exception:
                phase = 0

            route = Route(
                title=str(r.get("title", "Route")).strip() or "Route",
                description=str(r.get("description", "")),
                tasks=parse_tasks(r, route_title=str(r.get("title", "Route")) or "Route"),
                kind=kind,
                phase=phase,
            )
            routes.append(route)
            key_to_route[key] = route

            if progress_events is None or len(progress_events) < 25:
                _emit_progress(
                    progress_events, emit, level="info", message=f"Route gelesen: {route.title}"
                )

        if not routes:
            raise ValueError("No routes found in plan")

        raw_edges = parsed.get("edges") or []
        if not isinstance(raw_edges, list):
            raise ValueError("edges must be a list")

        for e in raw_edges:
            if not isinstance(e, dict):
                continue
            raw_from = e.get("from") or e.get("from_route_id") or e.get("from_route")
            raw_to = e.get("to") or e.get("to_route_id") or e.get("to_route")
            from_key = str(raw_from).strip() if raw_from is not None else ""
            to_key = str(raw_to).strip() if raw_to is not None else ""
            if not from_key or not to_key:
                raise ValueError("edges entries must have from/to")
            if from_key not in key_to_route or to_key not in key_to_route:
                raise ValueError("edges refer to unknown route id")
            edges.append(
                GraphEdge(
                    from_route_id=key_to_route[from_key].id,
                    to_route_id=key_to_route[to_key].id,
                )
            )

        raw_decisions = parsed.get("decisions") or []
        if raw_decisions is not None and not isinstance(raw_decisions, list):
            raise ValueError("decisions must be a list")

        for di, d in enumerate(raw_decisions or []):
            if not isinstance(d, dict):
                continue

            raw_from = d.get("from") or d.get("from_route_id") or d.get("from_route")
            from_key = str(raw_from).strip() if raw_from is not None else ""
            if not from_key or from_key not in key_to_route:
                raise ValueError("Decision.from_route_id must refer to an existing route")

            try:
                phase = int(d.get("phase", 0) or 0)
            except Exception:
                phase = 0

            opts: list[DecisionOption] = []
            for opt in d.get("options", []) or []:
                if not isinstance(opt, dict):
                    continue
                label = str(opt.get("label", "Option")).strip() or "Option"
                raw_target = opt.get("to") or opt.get("to_route_id") or opt.get("route_id")
                target_key = str(raw_target).strip() if raw_target is not None else ""
                if not target_key or target_key not in key_to_route:
                    raise ValueError("Decision option must refer to an existing route")
                opts.append(DecisionOption(label=label, route_id=key_to_route[target_key].id))

            if not opts:
                raise ValueError("decision.options must be non-empty")

            chosen_idx = d.get("chosen_option_index", 0)
            try:
                chosen_idx_int = int(chosen_idx)
            except Exception:
                chosen_idx_int = 0
            if not (0 <= chosen_idx_int < len(opts)):
                raise ValueError("Decision chosen_option_index out of bounds")
            chosen_option_id = opts[chosen_idx_int].id

            decisions.append(
                Decision(
                    title=str(d.get("title", "Weiche")).strip() or "Weiche",
                    prompt=str(d.get("prompt", "")),
                    options=opts,
                    chosen_option_id=chosen_option_id,
                    from_route_id=key_to_route[from_key].id,
                    phase=phase,
                )
            )

        # Be robust: ensure graph edges include the decision options.
        # Some model outputs provide `decisions` but omit or partially fill `edges`.
        existing_pairs = {(e.from_route_id, e.to_route_id) for e in edges}
        for d in decisions:
            if not d.from_route_id:
                continue
            for opt in d.options:
                pair = (d.from_route_id, opt.route_id)
                if pair in existing_pairs:
                    continue
                edges.append(GraphEdge(from_route_id=d.from_route_id, to_route_id=opt.route_id))
                existing_pairs.add(pair)

        # Active route: start at a root node (no incoming edges), otherwise first route.
        incoming_ids = {r.id: 0 for r in key_to_route.values()}
        for e in edges:
            if e.to_route_id in incoming_ids:
                incoming_ids[e.to_route_id] += 1
        roots = [rid for rid, deg in incoming_ids.items() if deg == 0]
        active_route_id = roots[0] if roots else next(iter(incoming_ids.keys()))

        return Goal(
            title=str(parsed.get("title", req.raw_goal)).strip() or req.raw_goal,
            description=str(parsed.get("description", "")),
            prologue=str(parsed.get("prologue", "")),
            rallying_cry=str(parsed.get("rallying_cry", "")),
            routes=routes,
            edges=edges,
            decisions=decisions,
            people=people,
            active_route_id=active_route_id,
        )

    # Schema: phases[] (multiple switches + merge)
    if parsed.get("phases"):
        phases = parsed.get("phases") or []
        if not isinstance(phases, list) or not phases:
            raise ValueError("phases must be a non-empty list")

        for i, ph in enumerate(phases):
            if not isinstance(ph, dict):
                continue
            try:
                phase = int(ph.get("phase", i))
            except Exception:
                phase = i

            trunk = ph.get("trunk") or {}
            if not isinstance(trunk, dict):
                raise ValueError("phase.trunk must be an object")
            trunk_route = Route(
                title=str(trunk.get("title", f"Abschnitt {phase + 1}")).strip()
                or f"Abschnitt {phase + 1}",
                description=str(trunk.get("description", "")),
                tasks=parse_tasks(
                    trunk, route_title=str(trunk.get("title", "")) or f"Abschnitt {phase + 1}"
                ),
                kind=RouteKind.trunk,
                phase=phase,
            )
            routes.append(trunk_route)

            decision = ph.get("decision")
            if not decision:
                continue
            if not isinstance(decision, dict):
                raise ValueError("phase.decision must be an object when present")

            opts: list[DecisionOption] = []
            for opt in decision.get("options", []) or []:
                if not isinstance(opt, dict):
                    continue
                label = str(opt.get("label", "Option")).strip() or "Option"
                branch = opt.get("branch") or {}
                if not isinstance(branch, dict):
                    raise ValueError("decision.options[].branch must be an object")
                branch_route = Route(
                    title=str(branch.get("title", label)).strip() or label,
                    description=str(branch.get("description", "")),
                    tasks=parse_tasks(branch, route_title=str(branch.get("title", "")) or label),
                    kind=RouteKind.branch,
                    phase=phase,
                )
                routes.append(branch_route)
                opts.append(DecisionOption(label=label, route_id=branch_route.id))

            if not opts:
                raise ValueError("decision.options must be non-empty")

            chosen_idx = decision.get("chosen_option_index", 0)
            try:
                chosen_idx_int = int(chosen_idx)
            except Exception:
                chosen_idx_int = 0
            if not (0 <= chosen_idx_int < len(opts)):
                raise ValueError("Decision chosen_option_index out of bounds")
            chosen_option_id = opts[chosen_idx_int].id

            decisions.append(
                Decision(
                    title=str(decision.get("title", "Weiche")).strip() or "Weiche",
                    prompt=str(decision.get("prompt", "")),
                    options=opts,
                    chosen_option_id=chosen_option_id,
                    phase=phase,
                )
            )

        if not routes:
            raise ValueError("No routes found in phases")
    else:
        # Legacy schema: routes[] + decisions[] route_index references
        for r in parsed.get("routes", []) or []:
            if not isinstance(r, dict):
                continue
            routes.append(
                Route(
                    title=str(r.get("title", "Route")).strip() or "Route",
                    description=str(r.get("description", "")),
                    tasks=parse_tasks(r, route_title=str(r.get("title", "Route")) or "Route"),
                    kind=RouteKind.branch,
                    phase=0,
                )
            )

        if not routes:
            raise ValueError("No routes found in plan")

        for d in parsed.get("decisions", []) or []:
            if not isinstance(d, dict):
                continue
            opts: list[DecisionOption] = []
            for opt in d.get("options", []) or []:
                if not isinstance(opt, dict):
                    continue
                label = str(opt.get("label", "Option")).strip() or "Option"
                idx = opt.get("route_index", 0)
                try:
                    idx_int = int(idx)
                except Exception:
                    idx_int = 0
                if not (0 <= idx_int < len(routes)):
                    raise ValueError("Decision option route_index out of bounds")
                route_id = routes[idx_int].id
                opts.append(DecisionOption(label=label, route_id=route_id))
            chosen_idx = d.get("chosen_option_index", 0)
            try:
                chosen_idx_int = int(chosen_idx)
            except Exception:
                chosen_idx_int = 0
            if opts and not (0 <= chosen_idx_int < len(opts)):
                raise ValueError("Decision chosen_option_index out of bounds")
            chosen_option_id = opts[chosen_idx_int].id if opts else None
            decisions.append(
                Decision(
                    title=str(d.get("title", "Weiche")).strip() or "Weiche",
                    prompt=str(d.get("prompt", "")),
                    options=opts,
                    chosen_option_id=chosen_option_id,
                    phase=0,
                )
            )

    active_route_id = routes[0].id
    if decisions:
        decisions_sorted = sorted(decisions, key=lambda d: int(d.phase))
        first = decisions_sorted[0]
        chosen = first.chosen_option_id or (first.options[0].id if first.options else None)
        if chosen:
            for opt in first.options:
                if opt.id == chosen:
                    active_route_id = opt.route_id
                    break

    return Goal(
        title=str(parsed.get("title", req.raw_goal)).strip() or req.raw_goal,
        description=str(parsed.get("description", "")),
        prologue=str(parsed.get("prologue", "")),
        rallying_cry=str(parsed.get("rallying_cry", "")),
        routes=routes,
        decisions=decisions,
        people=people,
        active_route_id=active_route_id,
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
    """OpenAI-kompatible Planung.

    Important: no heuristic fallback. Errors are returned explicitly.
    """

    if not settings.openai_api_key:
        await debug_log("error", "Planner: missing OPENAI_API_KEY")
        return PlanResult(goal=None, source="openai", error="missing_openai_api_key")

    prompt = (
        "Du bist ein Planungsassistent für eine App namens 'Stellwerk'.\n"
        "Ziel: Ein maximal detaillierter, VERZWEIGTER Plan als gerichteter azyklischer Graph (DAG) mit Merges.\n\n"
        "Anforderungen:\n"
        "- Bis zu 10 Abzweigungsebenen (Entscheidungen können auch auf Abzweigen erneut verzweigen).\n"
        "- Merges sind erlaubt (mehrere Kanten können wieder auf denselben Knoten zeigen).\n"
        "- Keine Zyklen (DAG). Der Graph muss am Ende zu einem Ziel-Endknoten führen.\n"
        "- 6–20 Knoten (routes) insgesamt.\n"
        "- Pro Route: 2–6 Aufgaben. Pro Aufgabe: 2–6 Arbeitspakete.\n\n"
        "WICHTIG: Arbeitspakete müssen nicht nur sagen WAS, sondern WIE.\n"
        "`notes` muss ausführliches Markdown enthalten: konkrete Schritte, Definition of Done, Risiken,\n"
        "und am Ende einen Abschnitt 'Quellen' mit 1–5 URLs. Optional: Bild-URLs als Liste im Text (z. B. unter 'Bilder').\n\n"
        "Schema (JSON):\n"
        "{\n"
        "  title, description, prologue, rallying_cry,\n"
        "  people:[{name, role:(companion|helper), direction:(with_me|ahead), notes}],\n"
        "  routes:[\n"
        "    {id, title, description, kind:(trunk|branch), phase, tasks:[{title, notes, work_packages:[{title, notes, length, grade}]}]}\n"
        "  ],\n"
        "  edges:[{from, to}],\n"
        "  decisions:[\n"
        "    {title, prompt, from, phase, options:[{label, to}], chosen_option_index}\n"
        "  ]\n"
        "}\n\n"
        "Regeln:\n"
        "- `routes[].id` sind kurze Strings (z. B. 'r0', 'r1', ...), die in edges/decisions referenziert werden.\n"
        "- `decisions[].from` referenziert den Knoten, an dem die Weiche sitzt.\n"
        "- `options[].to` referenziert den Zielknoten der Option.\n"
        "- chosen_option_index ist 0-basiert.\n"
        "- Antworte ausschließlich als JSON-Objekt in genau diesem Schema.\n\n"
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

    timeout = httpx.Timeout(
        settings.openai_timeout_seconds,
        connect=10.0,
        read=settings.openai_timeout_seconds,
        write=10.0,
        pool=10.0,
    )
    retryable_status = {429, 500, 502, 503, 504}

    await debug_log(
        "info",
        "Planner: calling OpenAI-compatible endpoint",
        {
            "base_url": settings.openai_base_url,
            "model": settings.openai_model,
            "timeout_seconds": settings.openai_timeout_seconds,
            "retries": settings.openai_retries,
        },
    )

    last_error: str | None = None
    for attempt in range(0, max(0, settings.openai_retries) + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)

            request_id = resp.headers.get("x-request-id") or resp.headers.get("x-requestid")
            await debug_log(
                "info",
                "Planner: OpenAI response",
                {"status": resp.status_code, "attempt": attempt + 1, "request_id": request_id},
            )

            if resp.status_code in retryable_status:
                last_error = (
                    "openai_rate_limited" if resp.status_code == 429 else "openai_server_error"
                )
                if attempt < settings.openai_retries:
                    await debug_log(
                        "warn",
                        "Planner: retrying OpenAI call",
                        {"status": resp.status_code, "attempt": attempt + 1, "error": last_error},
                    )
                    await asyncio.sleep(0.6 * (2**attempt))
                    continue
                return PlanResult(goal=None, source="openai", error=last_error)

            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            await debug_log(
                "info",
                "Planner: parsing content",
                {"chars": len(content or ""), "attempt": attempt + 1},
            )
            parsed = _extract_json_object(content)
            goal = parse_openai_plan(parsed, req)
            await debug_log(
                "info",
                "Planner: OpenAI plan parsed successfully",
                {
                    "routes": len(goal.routes),
                    "decisions": len(goal.decisions),
                    "people": len(goal.people),
                },
            )
            return PlanResult(goal=goal, source="openai")
        except httpx.ReadTimeout:
            last_error = "openai_timeout"
            await debug_log(
                "warn",
                "Planner: OpenAI ReadTimeout",
                {"attempt": attempt + 1, "timeout_seconds": settings.openai_timeout_seconds},
            )
            if attempt < settings.openai_retries:
                await asyncio.sleep(0.6 * (2**attempt))
                continue
            return PlanResult(goal=None, source="openai", error=last_error)
        except httpx.ConnectError:
            last_error = "openai_connect_error"
            await debug_log("warn", "Planner: OpenAI ConnectError", {"attempt": attempt + 1})
            if attempt < settings.openai_retries:
                await asyncio.sleep(0.6 * (2**attempt))
                continue
            return PlanResult(goal=None, source="openai", error=last_error)
        except ValueError as e:
            # Most likely: model returned JSON that doesn't match our expected schema.
            reason = str(e).strip()
            if len(reason) > 240:
                reason = reason[:240] + "…"
            last_error = f"openai_invalid_plan:{reason}" if reason else "openai_invalid_plan"
            await debug_log(
                "warn",
                "Planner: OpenAI failed",
                {"exc_type": e.__class__.__name__, "exc": str(e)[:300], "attempt": attempt + 1},
            )
            if attempt < settings.openai_retries:
                await asyncio.sleep(0.6 * (2**attempt))
                continue
            return PlanResult(goal=None, source="openai", error=last_error)
        except Exception as e:
            last_error = f"openai_failed:{e.__class__.__name__}"
            await debug_log(
                "warn",
                "Planner: OpenAI failed",
                {"exc_type": e.__class__.__name__, "exc": str(e)[:300], "attempt": attempt + 1},
            )
            if attempt < settings.openai_retries:
                await asyncio.sleep(0.6 * (2**attempt))
                continue
            return PlanResult(goal=None, source="openai", error=last_error)

    return PlanResult(goal=None, source="openai", error=last_error or "openai_failed")


async def openai_plan_with_progress(
    req: PlanRequest, *, emit: Callable[[dict[str, Any]], None] | None = None
) -> PlanResultWithProgress:
    """Like openai_plan, but also returns a list of lightweight progress events.

    Intended for UI toasts (not debug console). Keeps content non-sensitive.
    """

    progress: list[dict[str, Any]] = []

    if not settings.openai_api_key:
        _emit_progress(progress, emit, level="error", message="OPENAI_API_KEY fehlt")
        return PlanResultWithProgress(
            PlanResult(goal=None, source="openai", error="missing_openai_api_key"), progress
        )

    # We can't tap into token-by-token generation, but we can show meaningful stages.
    _emit_progress(progress, emit, level="info", message="KI: Anfrage wird vorbereitet")

    # Inline a small copy of openai_plan's call to keep behavior consistent,
    # but route parsing through parse_openai_plan(progress_events=...).
    prompt = (
        "Du bist ein Planungsassistent für eine App namens 'Stellwerk'.\n"
        "Ziel: Ein maximal detaillierter, VERZWEIGTER Plan als gerichteter azyklischer Graph (DAG) mit Merges.\n\n"
        "Anforderungen:\n"
        "- Bis zu 10 Abzweigungsebenen (Entscheidungen können auch auf Abzweigen erneut verzweigen).\n"
        "- Merges sind erlaubt (mehrere Kanten können wieder auf denselben Knoten zeigen).\n"
        "- Keine Zyklen (DAG). Der Graph muss am Ende zu einem Ziel-Endknoten führen.\n"
        "- 6–20 Knoten (routes) insgesamt.\n"
        "- Pro Route: 2–6 Aufgaben. Pro Aufgabe: 2–6 Arbeitspakete.\n\n"
        "WICHTIG: Arbeitspakete müssen nicht nur sagen WAS, sondern WIE.\n"
        "`notes` muss ausführliches Markdown enthalten: konkrete Schritte, Definition of Done, Risiken,\n"
        "und am Ende einen Abschnitt 'Quellen' mit 1–5 URLs. Optional: Bild-URLs als Liste im Text (z. B. unter 'Bilder').\n\n"
        "Schema (JSON):\n"
        "{\n"
        "  title, description, prologue, rallying_cry,\n"
        "  people:[{name, role:(companion|helper), direction:(with_me|ahead), notes}],\n"
        "  routes:[\n"
        "    {id, title, description, kind:(trunk|branch), phase, tasks:[{title, notes, work_packages:[{title, notes, length, grade}]}]}\n"
        "  ],\n"
        "  edges:[{from, to}],\n"
        "  decisions:[\n"
        "    {title, prompt, from, phase, options:[{label, to}], chosen_option_index}\n"
        "  ]\n"
        "}\n\n"
        "Regeln:\n"
        "- `routes[].id` sind kurze Strings (z. B. 'r0', 'r1', ...), die in edges/decisions referenziert werden.\n"
        "- `decisions[].from` referenziert den Knoten, an dem die Weiche sitzt.\n"
        "- `options[].to` referenziert den Zielknoten der Option.\n"
        "- chosen_option_index ist 0-basiert.\n"
        "- Antworte ausschließlich als JSON-Objekt in genau diesem Schema.\n\n"
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
        "response_format": {"type": "json_object"},
    }

    timeout = httpx.Timeout(
        settings.openai_timeout_seconds,
        connect=10.0,
        read=settings.openai_timeout_seconds,
        write=10.0,
        pool=10.0,
    )
    retryable_status = {429, 500, 502, 503, 504}

    _emit_progress(progress, emit, level="info", message="KI: Anfrage wird gesendet")

    last_error: str | None = None
    for attempt in range(0, max(0, settings.openai_retries) + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)

            if resp.status_code in retryable_status:
                last_error = (
                    "openai_rate_limited" if resp.status_code == 429 else "openai_server_error"
                )
                _emit_progress(
                    progress,
                    emit,
                    level="warn",
                    message="KI: temporäres Problem, versuche erneut",
                    data={"status": resp.status_code, "attempt": attempt + 1},
                )
                if attempt < settings.openai_retries:
                    await asyncio.sleep(0.6 * (2**attempt))
                    continue
                return PlanResultWithProgress(
                    PlanResult(goal=None, source="openai", error=last_error), progress
                )

            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            _emit_progress(progress, emit, level="info", message="KI: Antwort erhalten, parse JSON")
            parsed = _extract_json_object(content)

            # Collect parse events for toasts.
            goal = parse_openai_plan(parsed, req, progress_events=progress, emit=emit)
            _emit_progress(progress, emit, level="info", message="KI: Plan fertig")
            return PlanResultWithProgress(PlanResult(goal=goal, source="openai"), progress)
        except httpx.ReadTimeout:
            last_error = "openai_timeout"
            _emit_progress(
                progress,
                emit,
                level="warn",
                message="KI: Timeout, versuche erneut",
                data={"attempt": attempt + 1},
            )
            if attempt < settings.openai_retries:
                await asyncio.sleep(0.6 * (2**attempt))
                continue
            return PlanResultWithProgress(
                PlanResult(goal=None, source="openai", error=last_error), progress
            )
        except httpx.ConnectError:
            last_error = "openai_connect_error"
            _emit_progress(
                progress,
                emit,
                level="warn",
                message="KI: Verbindungsfehler, versuche erneut",
                data={"attempt": attempt + 1},
            )
            if attempt < settings.openai_retries:
                await asyncio.sleep(0.6 * (2**attempt))
                continue
            return PlanResultWithProgress(
                PlanResult(goal=None, source="openai", error=last_error), progress
            )
        except ValueError as e:
            reason = str(e).strip()
            if len(reason) > 240:
                reason = reason[:240] + "…"
            last_error = f"openai_invalid_plan:{reason}" if reason else "openai_invalid_plan"
            _emit_progress(
                progress,
                emit,
                level="error",
                message="KI: Ungültiger Plan",
                data={"error": last_error},
            )
            if attempt < settings.openai_retries:
                await asyncio.sleep(0.6 * (2**attempt))
                continue
            return PlanResultWithProgress(
                PlanResult(goal=None, source="openai", error=last_error), progress
            )
        except Exception as e:
            last_error = f"openai_failed:{e.__class__.__name__}"
            _emit_progress(
                progress,
                emit,
                level="error",
                message="KI: Fehler",
                data={"type": e.__class__.__name__},
            )
            if attempt < settings.openai_retries:
                await asyncio.sleep(0.6 * (2**attempt))
                continue
            return PlanResultWithProgress(
                PlanResult(goal=None, source="openai", error=last_error), progress
            )

    return PlanResultWithProgress(
        PlanResult(goal=None, source="openai", error=last_error or "openai_failed"), progress
    )
