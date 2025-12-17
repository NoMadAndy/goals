from __future__ import annotations

from contextlib import asynccontextmanager
import time
from typing import AsyncGenerator
from uuid import UUID

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from stellwerk.db import create_db_engine, ensure_schema, init_db, open_session
from stellwerk.debug import debug_log, debug_snapshot, debug_subscribe, debug_unsubscribe, sse_encode
from stellwerk.models import WorkPackageStatus
from stellwerk.planner import PlanRequest, openai_plan
from stellwerk.repository import (
    apply_plan,
    create_goal as repo_create_goal,
    get_goal as repo_get_goal,
    get_work_package,
    list_goals as repo_list_goals,
    toggle_work_package,
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
            "db": "sqlite" if settings.database_url.startswith("sqlite") else "postgres" if settings.database_url.startswith("postgres") else "other",
            "openai_configured": bool(settings.openai_api_key),
            "openai_base_url": settings.openai_base_url,
            "openai_model": settings.openai_model,
        },
    )
    yield


app = FastAPI(title="Stellwerk", lifespan=lifespan)


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


class PlanApiRequest(BaseModel):
    raw_goal: str
    context: str = ""


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, goal: str | None = None):
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

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "app_title": "Stellwerk",
            "goals": goals,
            "selected_goal": selected_goal,
            "persistence": _persistence_label(settings.database_url),
            "debug_enabled": settings.stellwerk_debug,
        },
    )


@app.post("/api/plan")
async def api_plan(req: PlanApiRequest):
    await _dbg("info", "Plan API: requested", {"has_context": bool(req.context), "goal_len": len(req.raw_goal or "")})
    result = await openai_plan(PlanRequest(raw_goal=req.raw_goal, context=req.context))
    payload = result.goal.model_dump(mode="json")
    payload["plan_source"] = result.source
    if result.error:
        payload["plan_error"] = result.error
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


@app.post("/goals/{goal_id}/plan")
async def plan_goal(goal_id: UUID, context: str = Form("")):
    with open_session(engine) as session:
        existing = repo_get_goal(session, goal_id)

    if not existing:
        return RedirectResponse(url="/", status_code=303)

    await _dbg("info", "Plan: requested", {"goal_id": str(goal_id), "has_context": bool(context.strip())})
    result = await openai_plan(PlanRequest(raw_goal=existing.title, context=context.strip()))
    with open_session(engine) as session:
        apply_plan(session, goal_id, result.goal, plan_source=result.source)

    await _dbg(
        "info",
        "Plan: applied",
        {
            "goal_id": str(goal_id),
            "source": result.source,
            "tasks": len(result.goal.tasks),
            "work_packages": sum(len(t.work_packages) for t in result.goal.tasks),
        },
    )

    return RedirectResponse(url=f"/?goal={goal_id}", status_code=303)


@app.post("/goals/{goal_id}/packages/{package_id}/toggle")
async def toggle_package(goal_id: UUID, package_id: UUID):
    with open_session(engine) as session:
        toggle_work_package(session, package_id)
    await _dbg("info", "WorkPackage: toggled", {"goal_id": str(goal_id), "package_id": str(package_id)})
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

    return StreamingResponse(gen(), media_type="text/event-stream")
