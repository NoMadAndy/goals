from __future__ import annotations

from contextlib import asynccontextmanager
import time
from typing import AsyncGenerator
from uuid import UUID
import asyncio

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from stellwerk.db import create_db_engine, ensure_schema, init_db, open_session
from stellwerk.debug import (
    debug_log,
    debug_snapshot,
    debug_subscribe,
    debug_unsubscribe,
    sse_encode,
)
from stellwerk.models import PersonDirection, PersonRole, WorkPackageStatus
from stellwerk.notes import default_work_package_details
from stellwerk.planner import PlanRequest, openai_plan, openai_plan_with_progress
from stellwerk.repository import (
    apply_plan,
    choose_decision_option,
    create_goal as repo_create_goal,
    delete_goal as repo_delete_goal,
    delete_person,
    get_goal as repo_get_goal,
    get_work_package,
    list_goals as repo_list_goals,
    add_person,
    toggle_work_package,
    update_person,
    update_work_package,
)
from stellwerk.settings import settings


def _persistence_label(database_url: str) -> str:
    if database_url.startswith("sqlite"):
        return "SQLite"
    if database_url.startswith("postgres"):
        return "Postgres"
    return "Datenbank"


engine = create_db_engine()


async def _dbg(level: str, message: str, data: dict | None = None) -> None:
    if settings.stellwerk_debug:
        await debug_log(level, message, data)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db(engine)
    ensure_schema(engine)
    await _dbg(
        "info",
        "App: startup",
        {
            "debug": settings.stellwerk_debug,
            "db": "sqlite"
            if settings.database_url.startswith("sqlite")
            else "postgres"
            if settings.database_url.startswith("postgres")
            else "other",
            "openai_configured": bool(settings.openai_api_key),
            "openai_base_url": settings.openai_base_url,
            "openai_model": settings.openai_model,
        },
    )
    yield


app = FastAPI(title="Goals", lifespan=lifespan)


@app.middleware("http")
async def request_debug_middleware(request: Request, call_next):
    if not settings.stellwerk_debug:
        return await call_next(request)

    start = time.perf_counter()
    await _dbg(
        "info",
        "HTTP: request",
        {
            "method": request.method,
            "path": request.url.path,
            "query": request.url.query,
        },
    )
    try:
        response = await call_next(request)
        ms = int((time.perf_counter() - start) * 1000)
        await _dbg(
            "info",
            "HTTP: response",
            {
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": ms,
            },
        )
        return response
    except Exception as e:
        ms = int((time.perf_counter() - start) * 1000)
        await _dbg(
            "error",
            "HTTP: exception",
            {
                "method": request.method,
                "path": request.url.path,
                "ms": ms,
                "exc_type": e.__class__.__name__,
                "exc": str(e)[:300],
            },
        )
        raise


app.mount("/static", StaticFiles(directory="src/stellwerk/static"), name="static")
templates = Jinja2Templates(directory="src/stellwerk/templates")

# Templates: helper for rich work package details.
templates.env.filters["wp_details"] = lambda notes, title="": default_work_package_details(
    title=str(title or ""),
    notes=str(notes or ""),
)


class PlanApiRequest(BaseModel):
    raw_goal: str
    context: str = ""


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, goal: str | None = None, plan_error: str | None = None):
    with open_session(engine) as session:
        goals = repo_list_goals(session)

    selected = goals[0].id if goals else None
    if goal:
        try:
            selected = UUID(goal)
        except Exception:
            pass

    selected_goal = None
    if selected:
        with open_session(engine) as session:
            selected_goal = repo_get_goal(session, selected)

    selected_route = selected_goal.selected_route() if selected_goal else None
    path_routes = selected_goal.selected_path_routes() if selected_goal else []

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "app_title": "Goals",
            "goals": goals,
            "selected_goal": selected_goal,
            "selected_route": selected_route,
            "path_routes": path_routes,
            "persistence": _persistence_label(settings.database_url),
            "debug_enabled": settings.stellwerk_debug,
            "plan_error": plan_error,
        },
    )


@app.post("/api/plan")
async def api_plan(req: PlanApiRequest):
    await _dbg(
        "info",
        "Plan API: requested",
        {"has_context": bool(req.context), "goal_len": len(req.raw_goal or "")},
    )
    result = await openai_plan(PlanRequest(raw_goal=req.raw_goal, context=req.context))
    if not result.goal:
        return JSONResponse(
            {
                "plan_source": result.source,
                "plan_error": result.error or "openai_failed",
            },
            status_code=400,
        )
    payload = result.goal.model_dump(mode="json")
    payload["plan_source"] = result.source
    return JSONResponse(payload)


@app.post("/goals")
async def create_goal(title: str = Form(""), description: str = Form("")):
    title = title.strip()
    if not title:
        return RedirectResponse(url="/", status_code=303)

    with open_session(engine) as session:
        goal_id = repo_create_goal(session, title=title, description=description.strip())

    await _dbg("info", "Goal: created", {"goal_id": str(goal_id), "title": title})

    return RedirectResponse(url=f"/?goal={goal_id}", status_code=303)


@app.post("/goals/{goal_id}/delete")
async def delete_goal(goal_id: UUID):
    with open_session(engine) as session:
        repo_delete_goal(session, goal_id)
    await _dbg("info", "Goal: deleted", {"goal_id": str(goal_id)})
    return RedirectResponse(url="/", status_code=303)


@app.post("/goals/{goal_id}/plan")
async def plan_goal(goal_id: UUID, context: str = Form("")):
    with open_session(engine) as session:
        existing = repo_get_goal(session, goal_id)

    if not existing:
        return RedirectResponse(url="/", status_code=303)

    await _dbg(
        "info", "Plan: requested", {"goal_id": str(goal_id), "has_context": bool(context.strip())}
    )
    result = await openai_plan(PlanRequest(raw_goal=existing.title, context=context.strip()))

    if not result.goal:
        await _dbg(
            "error",
            "Plan: failed",
            {"goal_id": str(goal_id), "error": result.error or "openai_failed"},
        )
        return RedirectResponse(
            url=f"/?goal={goal_id}&plan_error={result.error or 'openai_failed'}", status_code=303
        )

    with open_session(engine) as session:
        apply_plan(session, goal_id, result.goal, plan_source=result.source)

    await _dbg(
        "info",
        "Plan: applied",
        {
            "goal_id": str(goal_id),
            "source": result.source,
            "routes": len(result.goal.routes),
            "decisions": len(result.goal.decisions),
            "people": len(result.goal.people),
            "tasks": sum(len(r.tasks) for r in result.goal.routes),
            "work_packages": sum(len(t.work_packages) for r in result.goal.routes for t in r.tasks),
        },
    )

    return RedirectResponse(url=f"/?goal={goal_id}", status_code=303)


@app.post("/goals/{goal_id}/plan/stream")
async def plan_goal_stream(goal_id: UUID, context: str = Form("")) -> StreamingResponse:
    """Plan creation with live progress updates for the UI.

    Streams SSE events (data: JSON) so the browser can show toast updates.
    """

    async def gen() -> AsyncGenerator[str, None]:
        async def _log_plan_event(ev: dict) -> None:
            if not settings.stellwerk_debug:
                return
            step = str(ev.get("step") or "")
            msg = str(ev.get("message") or "")
            lvl = str(ev.get("level") or "info")
            data = ev.get("data") if isinstance(ev.get("data"), dict) else None
            await _dbg(lvl, f"Plan: {step} {msg}".strip(), data)

        start_ev = {"level": "info", "message": "KI: Planung startet", "step": "stream.start"}
        await _log_plan_event(start_ev)
        yield sse_encode(start_ev)

        with open_session(engine) as session:
            existing = repo_get_goal(session, goal_id)

        if not existing:
            yield sse_encode({"level": "error", "message": "Ziel nicht gefunden", "redirect": "/"})
            return

        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=200)

        def emit(ev: dict) -> None:
            try:
                q.put_nowait(ev)
            except Exception:
                pass

        started = time.perf_counter()
        task = asyncio.create_task(
            openai_plan_with_progress(
                PlanRequest(raw_goal=existing.title, context=context.strip()),
                emit=emit,
            )
        )

        last_heartbeat = 0.0
        while not task.done():
            try:
                ev = await asyncio.wait_for(q.get(), timeout=1.0)
                if isinstance(ev, dict):
                    await _log_plan_event(ev)
                    yield sse_encode(ev)
            except asyncio.TimeoutError:
                pass

            # Heartbeat every ~2s so the user always sees it's still working.
            elapsed = time.perf_counter() - started
            if elapsed - last_heartbeat >= 2.0:
                last_heartbeat = elapsed
                hb = {
                    "level": "info",
                    "message": "KI: arbeitet noch…",
                    "step": "stream.heartbeat",
                    "data": {"seconds": int(elapsed)},
                }
                await _log_plan_event(hb)
                yield sse_encode(hb)

        # Drain remaining events
        while True:
            try:
                ev = q.get_nowait()
                if isinstance(ev, dict):
                    await _log_plan_event(ev)
                    yield sse_encode(ev)
            except Exception:
                break

        try:
            result_with_progress = await task
            result = result_with_progress.result
        except Exception as e:
            await _dbg(
                "error",
                "Plan stream: failed",
                {"goal_id": str(goal_id), "exc_type": e.__class__.__name__},
            )
            yield sse_encode({"level": "error", "message": "Planstream: Serverfehler"})
            yield sse_encode({"redirect": f"/?goal={goal_id}&plan_error=server_error"})
            return

        if not result.goal:
            err = result.error or "openai_failed"
            yield sse_encode(
                {
                    "level": "error",
                    "message": "Plan konnte nicht erstellt werden",
                    "step": "stream.plan_failed",
                    "data": {"error": err},
                }
            )
            yield sse_encode({"redirect": f"/?goal={goal_id}&plan_error={err}"})
            return

        saving = {"level": "info", "message": "Plan: wird gespeichert", "step": "stream.apply_plan"}
        await _log_plan_event(saving)
        yield sse_encode(saving)
        with open_session(engine) as session:
            apply_plan(session, goal_id, result.goal, plan_source=result.source)
        done = {"level": "info", "message": "Fertig", "step": "stream.done"}
        await _log_plan_event(done)
        yield sse_encode(done)
        yield sse_encode({"redirect": f"/?goal={goal_id}"})

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)


@app.post("/goals/{goal_id}/packages/{package_id}/toggle")
async def toggle_package(goal_id: UUID, package_id: UUID):
    with open_session(engine) as session:
        toggle_work_package(session, package_id)
    await _dbg(
        "info", "WorkPackage: toggled", {"goal_id": str(goal_id), "package_id": str(package_id)}
    )
    return RedirectResponse(url=f"/?goal={goal_id}", status_code=303)


@app.post("/goals/{goal_id}/decisions/{decision_id}/options/{option_id}/choose")
async def choose_option(goal_id: UUID, decision_id: UUID, option_id: UUID):
    with open_session(engine) as session:
        choose_decision_option(session, goal_id, decision_id, option_id)
    await _dbg(
        "info",
        "Decision: chosen",
        {"goal_id": str(goal_id), "decision_id": str(decision_id), "option_id": str(option_id)},
    )
    return RedirectResponse(url=f"/?goal={goal_id}", status_code=303)


@app.post("/goals/{goal_id}/people/add")
async def people_add(
    goal_id: UUID,
    name: str = Form(""),
    role: str = Form("companion"),
    direction: str = Form("with_me"),
    notes: str = Form(""),
):
    name = name.strip()
    if not name:
        return RedirectResponse(url=f"/?goal={goal_id}", status_code=303)
    try:
        role_enum = PersonRole(role)
    except Exception:
        role_enum = PersonRole.companion
    try:
        direction_enum = PersonDirection(direction)
    except Exception:
        direction_enum = PersonDirection.with_me

    with open_session(engine) as session:
        add_person(
            session, goal_id, name=name, role=role_enum, direction=direction_enum, notes=notes
        )
    await _dbg(
        "info",
        "People: added",
        {
            "goal_id": str(goal_id),
            "name": name,
            "role": role_enum.value,
            "direction": direction_enum.value,
        },
    )
    return RedirectResponse(url=f"/?goal={goal_id}", status_code=303)


@app.post("/goals/{goal_id}/people/{person_id}/update")
async def people_update(
    goal_id: UUID,
    person_id: UUID,
    name: str = Form(""),
    role: str = Form("companion"),
    direction: str = Form("with_me"),
    notes: str = Form(""),
):
    try:
        role_enum = PersonRole(role)
    except Exception:
        role_enum = PersonRole.companion
    try:
        direction_enum = PersonDirection(direction)
    except Exception:
        direction_enum = PersonDirection.with_me

    with open_session(engine) as session:
        update_person(
            session,
            goal_id,
            person_id,
            name=name,
            role=role_enum,
            direction=direction_enum,
            notes=notes,
        )
    await _dbg(
        "info",
        "People: updated",
        {
            "goal_id": str(goal_id),
            "person_id": str(person_id),
            "role": role_enum.value,
            "direction": direction_enum.value,
        },
    )
    return RedirectResponse(url=f"/?goal={goal_id}", status_code=303)


@app.post("/goals/{goal_id}/people/{person_id}/delete")
async def people_delete(goal_id: UUID, person_id: UUID):
    with open_session(engine) as session:
        delete_person(session, goal_id, person_id)
    await _dbg("info", "People: deleted", {"goal_id": str(goal_id), "person_id": str(person_id)})
    return RedirectResponse(url=f"/?goal={goal_id}", status_code=303)


@app.get("/goals/{goal_id}/packages/{package_id}", response_class=HTMLResponse)
async def work_package_details(request: Request, goal_id: UUID, package_id: UUID):
    with open_session(engine) as session:
        goal = repo_get_goal(session, goal_id)
        wp_info = get_work_package(session, package_id)

    if not goal or not wp_info:
        return RedirectResponse(url=f"/?goal={goal_id}", status_code=303)

    inferred_goal_id, task_title, wp = wp_info
    if inferred_goal_id != goal_id:
        return RedirectResponse(url=f"/?goal={goal_id}", status_code=303)

    return templates.TemplateResponse(
        request,
        "work_package.html",
        {
            "app_title": "Stellwerk",
            "goal": goal,
            "task_title": task_title,
            "wp": wp,
            "persistence": _persistence_label(settings.database_url),
            "debug_enabled": settings.stellwerk_debug,
        },
    )


@app.post("/goals/{goal_id}/packages/{package_id}")
async def work_package_update(
    goal_id: UUID,
    package_id: UUID,
    title: str = Form(""),
    notes: str = Form(""),
    length: int = Form(1),
    grade: int = Form(0),
    status: str = Form("todo"),
):
    try:
        status_enum = WorkPackageStatus(status)
    except Exception:
        status_enum = WorkPackageStatus.todo

    with open_session(engine) as session:
        update_work_package(
            session,
            package_id,
            title=title,
            notes=notes,
            length=length,
            grade=grade,
            status=status_enum,
        )

    await _dbg(
        "info",
        "WorkPackage: updated",
        {
            "goal_id": str(goal_id),
            "package_id": str(package_id),
            "status": status_enum.value,
            "length": int(length),
            "grade": int(grade),
            "notes_len": len(notes or ""),
        },
    )

    return RedirectResponse(url=f"/goals/{goal_id}/packages/{package_id}", status_code=303)


@app.get("/debug/snapshot")
async def debug_snapshot_route():
    if not settings.stellwerk_debug:
        return JSONResponse({"enabled": False, "events": []})
    return JSONResponse({"enabled": True, "events": await debug_snapshot()})


@app.get("/debug/stream")
async def debug_stream_route() -> StreamingResponse:
    if not settings.stellwerk_debug:
        return StreamingResponse(iter(()), media_type="text/event-stream")

    async def gen() -> AsyncGenerator[str, None]:
        q = await debug_subscribe()
        try:
            # send a tiny hello so UI can show connection state
            yield sse_encode({"level": "info", "message": "debug stream connected"})
            while True:
                event = await q.get()
                yield sse_encode(event.to_dict())
        finally:
            await debug_unsubscribe(q)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)
