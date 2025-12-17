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

    tasks: Mapped[list[TaskRow]] = relationship(
        back_populates="goal",
        cascade="all, delete-orphan",
        order_by="TaskRow.position",
    )


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    goal_id: Mapped[str] = mapped_column(String(36), ForeignKey("goals.id", ondelete="CASCADE"))

    title: Mapped[str] = mapped_column(String(240), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    goal: Mapped[GoalRow] = relationship(back_populates="tasks")
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


def open_session(engine: Engine) -> Session:
    return Session(engine)
