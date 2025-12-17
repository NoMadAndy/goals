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


class PersonRole(str, Enum):
    companion = "companion"  # zieht mit dir zusammen
    helper = "helper"  # du gehst voran / sie helfen aus anderer Perspektive


class PersonDirection(str, Enum):
    with_me = "with_me"  # gemeinsam ziehen
    ahead = "ahead"  # du gehst voran / die Person folgt dir oder du führst


class Person(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    role: PersonRole = PersonRole.companion
    direction: PersonDirection = PersonDirection.with_me
    notes: str = ""


class Route(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str = ""
    tasks: list[Task] = Field(default_factory=list)


class DecisionOption(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    label: str
    route_id: UUID


class Decision(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    prompt: str = ""
    options: list[DecisionOption] = Field(default_factory=list)
    chosen_option_id: UUID | None = None


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

    routes: list[Route] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    people: list[Person] = Field(default_factory=list)

    # UI: welche Route ist aktuell "gestellt" (wenn keine Decision vorhanden)
    active_route_id: UUID | None = None

    # Motivierende, "schöne Worte" (KI oder Heuristik)
    prologue: str = ""
    rallying_cry: str = ""

    # UI/Debug: Quelle des zuletzt angewendeten Plans
    plan_source: str = ""

    def selected_route(self) -> Route | None:
        if self.routes:
            # Prefer the chosen decision option (first decision acts as the main switch).
            if self.decisions:
                d = self.decisions[0]
                if d.chosen_option_id:
                    for opt in d.options:
                        if opt.id == d.chosen_option_id:
                            for r in self.routes:
                                if r.id == opt.route_id:
                                    return r
            if self.active_route_id:
                for r in self.routes:
                    if r.id == self.active_route_id:
                        return r
            return self.routes[0]
        return None
