from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from stellwerk.settings import settings


class Base(DeclarativeBase):
    pass


class GoalRow(Base):
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    prologue: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rallying_cry: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Last planning source ("openai" | "heuristic" | "")
    plan_source: Mapped[str] = mapped_column(String(32), nullable=False, default="")

    # Active route when no decision is used (or as a cached selection)
    active_route_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")

    # Legacy: tasks (kept for early DBs); new plans primarily use routes.
    tasks: Mapped[list["TaskRow"]] = relationship(
        back_populates="goal",
        cascade="all, delete-orphan",
        order_by="TaskRow.position",
    )

    routes: Mapped[list["RouteRow"]] = relationship(
        "RouteRow",
        back_populates="goal",
        cascade="all, delete-orphan",
        order_by="RouteRow.position",
    )
    decisions: Mapped[list["DecisionRow"]] = relationship(
        "DecisionRow",
        back_populates="goal",
        cascade="all, delete-orphan",
        order_by="DecisionRow.position",
    )
    people: Mapped[list["PersonRow"]] = relationship(
        "PersonRow",
        back_populates="goal",
        cascade="all, delete-orphan",
        order_by="PersonRow.position",
    )


class RouteRow(Base):
    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    goal_id: Mapped[str] = mapped_column(String(36), ForeignKey("goals.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    goal: Mapped["GoalRow"] = relationship("GoalRow", back_populates="routes")
    tasks: Mapped[list["TaskRow"]] = relationship(
        "TaskRow",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="TaskRow.position",
    )


class DecisionRow(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    goal_id: Mapped[str] = mapped_column(String(36), ForeignKey("goals.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chosen_option_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")

    goal: Mapped["GoalRow"] = relationship("GoalRow", back_populates="decisions")
    options: Mapped[list["DecisionOptionRow"]] = relationship(
        "DecisionOptionRow",
        back_populates="decision",
        cascade="all, delete-orphan",
        order_by="DecisionOptionRow.position",
    )


class DecisionOptionRow(Base):
    __tablename__ = "decision_options"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    decision_id: Mapped[str] = mapped_column(String(36), ForeignKey("decisions.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(240), nullable=False)
    route_id: Mapped[str] = mapped_column(String(36), ForeignKey("routes.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    decision: Mapped["DecisionRow"] = relationship("DecisionRow", back_populates="options")


class PersonRow(Base):
    __tablename__ = "people"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    goal_id: Mapped[str] = mapped_column(String(36), ForeignKey("goals.id", ondelete="CASCADE"))

    name: Mapped[str] = mapped_column(String(240), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="companion")
    direction: Mapped[str] = mapped_column(String(32), nullable=False, default="with_me")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    goal: Mapped["GoalRow"] = relationship("GoalRow", back_populates="people")


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    goal_id: Mapped[str] = mapped_column(String(36), ForeignKey("goals.id", ondelete="CASCADE"))
    route_id: Mapped[str] = mapped_column(String(36), ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, default="")

    title: Mapped[str] = mapped_column(String(240), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    goal: Mapped["GoalRow"] = relationship("GoalRow", back_populates="tasks")
    route: Mapped["RouteRow"] = relationship("RouteRow", back_populates="tasks")
    work_packages: Mapped[list[WorkPackageRow]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="WorkPackageRow.position",
    )


class WorkPackageRow(Base):
    __tablename__ = "work_packages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"))

    title: Mapped[str] = mapped_column(String(240), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    length: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    grade: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="todo")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    task: Mapped[TaskRow] = relationship(back_populates="work_packages")


def create_db_engine() -> Engine:
    url = settings.database_url
    connect_args: dict[str, Any] = {}

    # SQLite needs this for multi-threaded FastAPI usage
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(url, connect_args=connect_args)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def ensure_schema(engine: Engine) -> None:
    """Best-effort, minimal schema evolution for early-stage app.

    This keeps existing SQLite/Postgres deployments working when we add small columns.
    """

    url = str(engine.url)
    with engine.begin() as conn:
        if url.startswith("sqlite"):
            cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(goals)").fetchall()]
            if "plan_source" not in cols:
                conn.exec_driver_sql("ALTER TABLE goals ADD COLUMN plan_source VARCHAR(32) NOT NULL DEFAULT ''")
            if "active_route_id" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE goals ADD COLUMN active_route_id VARCHAR(36) NOT NULL DEFAULT ''"
                )

            task_cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(tasks)").fetchall()]
            if "route_id" not in task_cols:
                conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN route_id VARCHAR(36) NOT NULL DEFAULT ''")

            # New tables (create_all won't alter existing DBs, but will create missing tables)
            Base.metadata.create_all(bind=conn)
        elif url.startswith("postgres"):
            # Add column if missing
            exists = conn.exec_driver_sql(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='goals' AND column_name='plan_source'
                """
            ).fetchone()
            if not exists:
                conn.exec_driver_sql("ALTER TABLE goals ADD COLUMN plan_source VARCHAR(32) NOT NULL DEFAULT ''")

            exists = conn.exec_driver_sql(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='goals' AND column_name='active_route_id'
                """
            ).fetchone()
            if not exists:
                conn.exec_driver_sql(
                    "ALTER TABLE goals ADD COLUMN active_route_id VARCHAR(36) NOT NULL DEFAULT ''"
                )

            exists = conn.exec_driver_sql(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='tasks' AND column_name='route_id'
                """
            ).fetchone()
            if not exists:
                conn.exec_driver_sql(
                    "ALTER TABLE tasks ADD COLUMN route_id VARCHAR(36) NOT NULL DEFAULT ''"
                )

            Base.metadata.create_all(bind=conn)


def open_session(engine: Engine) -> Session:
    return Session(engine)
