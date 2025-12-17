from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from stellwerk.db import GoalRow, TaskRow, WorkPackageRow
from stellwerk.models import Goal, GoalStatus, Task, WorkPackage, WorkPackageStatus


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
    )
    session.add(row)
    session.commit()
    _log(log, "info", "DB: goal inserted", {"goal_id": str(goal.id)})
    return goal.id


def apply_plan(session: Session, goal_id: UUID, planned: Goal, *, plan_source: str = "", log=None) -> None:
    row = session.get(GoalRow, str(goal_id))
    if not row:
        _log(log, "warn", "DB: apply_plan goal not found", {"goal_id": str(goal_id)})
        return

    row.description = planned.description or row.description
    row.prologue = planned.prologue
    row.rallying_cry = planned.rallying_cry
    row.plan_source = (plan_source or "").strip()
    _log(
        log,
        "info",
        "DB: apply_plan replacing tasks",
        {"goal_id": str(goal_id), "tasks": len(planned.tasks), "source": row.plan_source},
    )

    # Replace tasks/packages
    session.execute(delete(WorkPackageRow).where(WorkPackageRow.task_id.in_(select(TaskRow.id).where(TaskRow.goal_id == row.id))))
    session.execute(delete(TaskRow).where(TaskRow.goal_id == row.id))

    for ti, task in enumerate(planned.tasks):
        trow = TaskRow(
            id=str(task.id),
            goal_id=row.id,
            title=task.title,
            notes=task.notes,
            position=ti,
        )
        session.add(trow)
        for wi, wp in enumerate(task.work_packages):
            wprow = WorkPackageRow(
                id=str(wp.id),
                task_id=trow.id,
                title=wp.title,
                notes=wp.notes,
                length=max(1, int(wp.length)),
                grade=max(0, min(10, int(wp.grade))),
                status=wp.status.value,
                position=wi,
            )
            session.add(wprow)

    session.commit()
    _log(log, "info", "DB: apply_plan committed", {"goal_id": str(goal_id)})


def toggle_work_package(session: Session, package_id: UUID, *, log=None) -> None:
    row = session.get(WorkPackageRow, str(package_id))
    if not row:
        _log(log, "warn", "DB: toggle_work_package not found", {"package_id": str(package_id)})
        return

    row.status = "done" if row.status != "done" else "todo"
    session.commit()
    _log(log, "info", "DB: work_package toggled", {"package_id": str(package_id), "status": row.status})


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
        {"package_id": str(package_id), "status": row.status, "length": row.length, "grade": row.grade},
    )


def row_to_goal(row: GoalRow) -> Goal:
    tasks: list[Task] = []
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
        tasks.append(Task(id=UUID(t.id), title=t.title, notes=t.notes, work_packages=wps))

    return Goal(
        id=UUID(row.id),
        title=row.title,
        description=row.description,
        status=GoalStatus(row.status),
        created_at=row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc),
        tasks=tasks,
        prologue=row.prologue,
        rallying_cry=row.rallying_cry,
        plan_source=getattr(row, "plan_source", "") or "",
    )
