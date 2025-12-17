from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class WorkPackageStatus(str, Enum):
    todo = "todo"
    done = "done"
    diverted = "diverted"  # "Weiche gestellt": anderes Ergebnis/Route


class WorkPackage(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    notes: str = ""

    # Sichtbar als Streckenabschnitt
    length: int = 1  # grob: Aufwand (z. B. Stunden/Points)
    grade: int = 0  # grob: Steigung/Schwierigkeit 0-10

    status: WorkPackageStatus = WorkPackageStatus.todo


class Task(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    notes: str = ""
    work_packages: list[WorkPackage] = Field(default_factory=list)


class GoalStatus(str, Enum):
    planned = "planned"
    in_progress = "in_progress"
    achieved = "achieved"


class Goal(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str = ""

    status: GoalStatus = GoalStatus.planned
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    tasks: list[Task] = Field(default_factory=list)

    # Motivierende, "schöne Worte" (KI oder Heuristik)
    prologue: str = ""
    rallying_cry: str = ""

    # UI/Debug: Quelle des zuletzt angewendeten Plans
    plan_source: str = ""
