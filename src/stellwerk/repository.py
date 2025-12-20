from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from stellwerk.db import (
    DecisionOptionRow,
    DecisionRow,
    GoalRow,
    PersonRow,
    RouteRow,
    RouteEdgeRow,
    TaskRow,
    WorkPackageRow,
)
from stellwerk.models import (
    Decision,
    DecisionOption,
    GraphEdge,
    Goal,
    GoalStatus,
    Person,
    PersonDirection,
    PersonRole,
    Route,
    RouteKind,
    Task,
    WorkPackage,
    WorkPackageStatus,
)


def _log(log, level: str, message: str, data: dict | None = None) -> None:
    if log is None:
        return
    try:
        log(level, message, data)
    except Exception:
        # Logging must never break app flow.
        return


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def list_goals(session: Session) -> list[Goal]:
    rows = session.execute(select(GoalRow).order_by(GoalRow.created_at.desc())).scalars().all()
    return [row_to_goal(r) for r in rows]


def get_goal(session: Session, goal_id: UUID) -> Goal | None:
    row = session.get(GoalRow, str(goal_id))
    if not row:
        return None
    # relationships are lazy; access to load
    _ = row.routes
    _ = row.decisions
    _ = row.edges
    _ = row.people
    _ = row.tasks
    return row_to_goal(row)


def create_goal(session: Session, title: str, description: str, *, log=None) -> UUID:
    goal = Goal(title=title, description=description)

    row = GoalRow(
        id=str(goal.id),
        title=goal.title,
        description=goal.description,
        status=goal.status.value,
        created_at=goal.created_at,
        prologue=goal.prologue,
        rallying_cry=goal.rallying_cry,
        active_route_id="",
    )
    session.add(row)
    session.commit()
    _log(log, "info", "DB: goal inserted", {"goal_id": str(goal.id)})
    return goal.id


def apply_plan(
    session: Session, goal_id: UUID, planned: Goal, *, plan_source: str = "", log=None
) -> None:
    row = session.get(GoalRow, str(goal_id))
    if not row:
        _log(log, "warn", "DB: apply_plan goal not found", {"goal_id": str(goal_id)})
        return

    row.description = planned.description or row.description
    row.prologue = planned.prologue
    row.rallying_cry = planned.rallying_cry
    row.plan_source = (plan_source or "").strip()
    route_ids: set[str] = {str(r.id) for r in getattr(planned, "routes", []) or []}
    active_route_id = str(planned.active_route_id) if planned.active_route_id else ""
    if active_route_id and active_route_id not in route_ids:
        _log(
            log,
            "warn",
            "DB: apply_plan active_route_id not in routes; resetting",
            {"goal_id": str(goal_id), "active_route_id": active_route_id},
        )
        active_route_id = ""
    row.active_route_id = active_route_id
    _log(
        log,
        "info",
        "DB: apply_plan replacing graph",
        {
            "goal_id": str(goal_id),
            "routes": len(planned.routes),
            "decisions": len(planned.decisions),
            "people": len(planned.people),
            "source": row.plan_source,
        },
    )

    # Replace everything under this goal (best-effort, early-stage app)
    session.execute(
        delete(WorkPackageRow).where(
            WorkPackageRow.task_id.in_(select(TaskRow.id).where(TaskRow.goal_id == row.id))
        )
    )
    session.execute(delete(TaskRow).where(TaskRow.goal_id == row.id))
    session.execute(
        delete(DecisionOptionRow).where(
            DecisionOptionRow.decision_id.in_(
                select(DecisionRow.id).where(DecisionRow.goal_id == row.id)
            )
        )
    )
    session.execute(delete(DecisionRow).where(DecisionRow.goal_id == row.id))
    session.execute(delete(RouteEdgeRow).where(RouteEdgeRow.goal_id == row.id))
    session.execute(delete(RouteRow).where(RouteRow.goal_id == row.id))
    session.execute(delete(PersonRow).where(PersonRow.goal_id == row.id))

    # Insert people
    for pi, p in enumerate(planned.people):
        session.add(
            PersonRow(
                id=str(p.id),
                goal_id=row.id,
                name=p.name,
                role=p.role.value,
                direction=p.direction.value,
                notes=p.notes,
                position=pi,
            )
        )

    # Insert routes + tasks + work packages
    for ri, route in enumerate(planned.routes):
        rrow = RouteRow(
            id=str(route.id),
            goal_id=row.id,
            title=route.title,
            description=route.description,
            kind=getattr(route, "kind", RouteKind.trunk).value,
            phase=int(getattr(route, "phase", 0)),
            position=ri,
        )
        session.add(rrow)
        for ti, task in enumerate(route.tasks):
            trow = TaskRow(
                id=str(task.id),
                goal_id=row.id,
                route_id=rrow.id,
                title=task.title,
                notes=task.notes,
                position=ti,
            )
            session.add(trow)
            for wi, wp in enumerate(task.work_packages):
                session.add(
                    WorkPackageRow(
                        id=str(wp.id),
                        task_id=trow.id,
                        title=wp.title,
                        notes=wp.notes,
                        length=max(1, int(wp.length)),
                        grade=max(0, min(10, int(wp.grade))),
                        status=wp.status.value,
                        position=wi,
                    )
                )

    # Important for Postgres FK constraints:
    # Ensure routes exist in the DB before inserting decisions/options that FK to routes.
    session.flush()

    # Insert decisions/options
    decision_position = 0
    for d in planned.decisions:
        raw_from = getattr(d, "from_route_id", None)
        from_route_id = str(raw_from) if raw_from else ""

        if not from_route_id or from_route_id not in route_ids:
            _log(
                log,
                "warn",
                "DB: apply_plan skipping decision with missing from_route_id",
                {
                    "goal_id": str(goal_id),
                    "decision_id": str(d.id),
                    "from_route_id": from_route_id,
                },
            )
            continue

        valid_opts = [
            opt for opt in (getattr(d, "options", []) or []) if str(opt.route_id) in route_ids
        ]
        if not valid_opts:
            _log(
                log,
                "warn",
                "DB: apply_plan skipping decision with no valid options",
                {"goal_id": str(goal_id), "decision_id": str(d.id)},
            )
            continue

        chosen_option_id = str(getattr(d, "chosen_option_id", "") or "")
        if chosen_option_id and all(str(opt.id) != chosen_option_id for opt in valid_opts):
            chosen_option_id = ""

        drow = DecisionRow(
            id=str(d.id),
            goal_id=row.id,
            title=d.title,
            prompt=d.prompt,
            from_route_id=from_route_id,
            phase=int(getattr(d, "phase", 0)),
            position=decision_position,
            chosen_option_id=chosen_option_id,
        )
        session.add(drow)
        for oi, opt in enumerate(valid_opts):
            session.add(
                DecisionOptionRow(
                    id=str(opt.id),
                    decision_id=drow.id,
                    label=opt.label,
                    route_id=str(opt.route_id),
                    position=oi,
                )
            )
        decision_position += 1

    # Ensure decisions exist before options/edges dependent on them (best-effort ordering)
    session.flush()

    # Insert edges (DAG)
    edge_position = 0
    for e in getattr(planned, "edges", []) or []:
        from_id = str(e.from_route_id)
        to_id = str(e.to_route_id)
        if from_id not in route_ids or to_id not in route_ids:
            _log(
                log,
                "warn",
                "DB: apply_plan skipping edge with missing route",
                {
                    "goal_id": str(goal_id),
                    "edge_id": str(e.id),
                    "from_route_id": from_id,
                    "to_route_id": to_id,
                },
            )
            continue
        session.add(
            RouteEdgeRow(
                id=str(e.id),
                goal_id=row.id,
                from_route_id=from_id,
                to_route_id=to_id,
                position=edge_position,
            )
        )
        edge_position += 1

    session.commit()
    _log(log, "info", "DB: apply_plan committed", {"goal_id": str(goal_id)})


def choose_decision_option(
    session: Session, goal_id: UUID, decision_id: UUID, option_id: UUID
) -> None:
    drow = session.get(DecisionRow, str(decision_id))
    if not drow or drow.goal_id != str(goal_id):
        return
    drow.chosen_option_id = str(option_id)
    session.commit()


def add_person(
    session: Session,
    goal_id: UUID,
    *,
    name: str,
    role: PersonRole,
    direction: PersonDirection,
    notes: str,
) -> None:
    goal = session.get(GoalRow, str(goal_id))
    if not goal:
        return
    position = (
        session.execute(
            select(PersonRow)
            .where(PersonRow.goal_id == str(goal_id))
            .order_by(PersonRow.position.desc())
        )
        .scalars()
        .first()
    )
    next_pos = (position.position + 1) if position else 0
    p = Person(name=name.strip(), role=role, direction=direction, notes=notes)
    session.add(
        PersonRow(
            id=str(p.id),
            goal_id=str(goal_id),
            name=p.name,
            role=p.role.value,
            direction=p.direction.value,
            notes=p.notes,
            position=next_pos,
        )
    )
    session.commit()


def update_person(
    session: Session,
    goal_id: UUID,
    person_id: UUID,
    *,
    name: str,
    role: PersonRole,
    direction: PersonDirection,
    notes: str,
) -> None:
    row = session.get(PersonRow, str(person_id))
    if not row or row.goal_id != str(goal_id):
        return
    row.name = name.strip() or row.name
    row.role = role.value
    row.direction = direction.value
    row.notes = notes
    session.commit()


def delete_person(session: Session, goal_id: UUID, person_id: UUID) -> None:
    row = session.get(PersonRow, str(person_id))
    if not row or row.goal_id != str(goal_id):
        return
    session.delete(row)
    session.commit()


def toggle_work_package(session: Session, package_id: UUID, *, log=None) -> None:
    row = session.get(WorkPackageRow, str(package_id))
    if not row:
        _log(log, "warn", "DB: toggle_work_package not found", {"package_id": str(package_id)})
        return

    row.status = "done" if row.status != "done" else "todo"
    session.commit()
    _log(
        log,
        "info",
        "DB: work_package toggled",
        {"package_id": str(package_id), "status": row.status},
    )


def get_work_package(session: Session, package_id: UUID) -> tuple[UUID, str, WorkPackage] | None:
    stmt = (
        select(WorkPackageRow, TaskRow)
        .join(TaskRow, WorkPackageRow.task_id == TaskRow.id)
        .where(WorkPackageRow.id == str(package_id))
    )
    result = session.execute(stmt).first()
    if not result:
        return None

    wp_row, task_row = result
    wp = WorkPackage(
        id=UUID(wp_row.id),
        title=wp_row.title,
        notes=wp_row.notes,
        length=wp_row.length,
        grade=wp_row.grade,
        status=WorkPackageStatus(wp_row.status),
    )
    return UUID(task_row.goal_id), task_row.title, wp


def update_work_package(
    session: Session,
    package_id: UUID,
    *,
    title: str,
    notes: str,
    length: int,
    grade: int,
    status: WorkPackageStatus,
    log=None,
) -> None:
    row = session.get(WorkPackageRow, str(package_id))
    if not row:
        _log(log, "warn", "DB: update_work_package not found", {"package_id": str(package_id)})
        return

    row.title = title.strip() or row.title
    row.notes = notes
    row.length = max(1, int(length))
    row.grade = max(0, min(10, int(grade)))
    row.status = status.value
    session.commit()
    _log(
        log,
        "info",
        "DB: work_package updated",
        {
            "package_id": str(package_id),
            "status": row.status,
            "length": row.length,
            "grade": row.grade,
        },
    )


def row_to_goal(row: GoalRow) -> Goal:
    people: list[Person] = []
    for p in getattr(row, "people", []) or []:
        try:
            role = PersonRole(p.role)
        except Exception:
            role = PersonRole.companion
        try:
            direction = PersonDirection(p.direction)
        except Exception:
            direction = PersonDirection.with_me
        people.append(
            Person(id=UUID(p.id), name=p.name, role=role, direction=direction, notes=p.notes)
        )

    routes: list[Route] = []
    for r in getattr(row, "routes", []) or []:
        tasks: list[Task] = []
        for t in getattr(r, "tasks", []) or []:
            wps: list[WorkPackage] = []
            for wp in t.work_packages:
                wps.append(
                    WorkPackage(
                        id=UUID(wp.id),
                        title=wp.title,
                        notes=wp.notes,
                        length=wp.length,
                        grade=wp.grade,
                        status=WorkPackageStatus(wp.status),
                    )
                )
            tasks.append(Task(id=UUID(t.id), title=t.title, notes=t.notes, work_packages=wps))
        try:
            kind = RouteKind(getattr(r, "kind", "trunk") or "trunk")
        except Exception:
            kind = RouteKind.trunk
        routes.append(
            Route(
                id=UUID(r.id),
                title=r.title,
                description=r.description,
                tasks=tasks,
                kind=kind,
                phase=int(getattr(r, "phase", 0) or 0),
            )
        )

    decisions: list[Decision] = []
    for d in getattr(row, "decisions", []) or []:
        options: list[DecisionOption] = []
        for opt in getattr(d, "options", []) or []:
            options.append(
                DecisionOption(
                    id=UUID(opt.id),
                    label=opt.label,
                    route_id=UUID(opt.route_id),
                )
            )
        chosen = None
        if getattr(d, "chosen_option_id", ""):
            try:
                chosen = UUID(d.chosen_option_id)
            except Exception:
                chosen = None
        decisions.append(
            Decision(
                id=UUID(d.id),
                title=d.title,
                prompt=d.prompt,
                options=options,
                chosen_option_id=chosen,
                from_route_id=UUID(d.from_route_id) if getattr(d, "from_route_id", "") else None,
                phase=int(getattr(d, "phase", 0) or 0),
            )
        )

    edges: list[GraphEdge] = []
    for e in getattr(row, "edges", []) or []:
        try:
            edges.append(
                GraphEdge(
                    id=UUID(e.id),
                    from_route_id=UUID(e.from_route_id),
                    to_route_id=UUID(e.to_route_id),
                )
            )
        except Exception:
            continue

    # Legacy compatibility: if there are tasks directly on the goal but no routes yet, wrap into a default route.
    if not routes and getattr(row, "tasks", None):
        legacy_tasks: list[Task] = []
        for t in row.tasks:
            wps: list[WorkPackage] = []
            for wp in t.work_packages:
                wps.append(
                    WorkPackage(
                        id=UUID(wp.id),
                        title=wp.title,
                        notes=wp.notes,
                        length=wp.length,
                        grade=wp.grade,
                        status=WorkPackageStatus(wp.status),
                    )
                )
            legacy_tasks.append(
                Task(id=UUID(t.id), title=t.title, notes=t.notes, work_packages=wps)
            )
        routes = [
            Route(
                title="Standardroute",
                description="(Altbestand)",
                tasks=legacy_tasks,
                kind=RouteKind.trunk,
                phase=0,
            )
        ]

    return Goal(
        id=UUID(row.id),
        title=row.title,
        description=row.description,
        status=GoalStatus(row.status),
        created_at=row.created_at
        if row.created_at.tzinfo
        else row.created_at.replace(tzinfo=timezone.utc),
        routes=routes,
        decisions=decisions,
        people=people,
        edges=edges,
        prologue=row.prologue,
        rallying_cry=row.rallying_cry,
        plan_source=getattr(row, "plan_source", "") or "",
        active_route_id=UUID(row.active_route_id) if getattr(row, "active_route_id", "") else None,
    )
