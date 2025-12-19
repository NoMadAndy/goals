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

    # Branching/graph metadata
    kind: "RouteKind" = Field(default_factory=lambda: RouteKind.trunk)
    phase: int = 0


class RouteKind(str, Enum):
    trunk = "trunk"  # gemeinsamer Abschnitt
    branch = "branch"  # Alternative bei einer Weiche


class DecisionOption(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    label: str
    route_id: UUID  # target node (Route) id


class Decision(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    prompt: str = ""
    options: list[DecisionOption] = Field(default_factory=list)
    chosen_option_id: UUID | None = None
    # Graph: decision is attached to a node ("from")
    from_route_id: UUID | None = None
    # Legacy/ordering hint
    phase: int = 0


class GraphEdge(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    from_route_id: UUID
    to_route_id: UUID


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

    # Graph edges between routes (DAG). If empty, fall back to legacy phase model.
    edges: list[GraphEdge] = Field(default_factory=list)

    # UI: welche Route ist aktuell "gestellt" (wenn keine Decision vorhanden)
    active_route_id: UUID | None = None

    # Motivierende, "schöne Worte" (KI)
    prologue: str = ""
    rallying_cry: str = ""

    # UI/Debug: Quelle des zuletzt angewendeten Plans
    plan_source: str = ""

    def selected_path_routes(self) -> list[Route]:
        """Return the active path through the plan.

        - If `edges` exist, interpret routes as nodes in a DAG (merges allowed).
          Traversal follows decisions (attached to nodes) to select outgoing edges.
          Safety: hard stop after 50 hops and an effective branching depth of 10.
        - If no edges exist, fall back to the legacy phase model.
        """

        if not self.routes:
            return []

        # New: graph traversal
        if self.edges:
            routes_by_id: dict[UUID, Route] = {r.id: r for r in self.routes}

            incoming: dict[UUID, int] = {r.id: 0 for r in self.routes}
            outgoing: dict[UUID, list[UUID]] = {r.id: [] for r in self.routes}
            for e in self.edges:
                if e.from_route_id in outgoing:
                    outgoing[e.from_route_id].append(e.to_route_id)
                if e.to_route_id in incoming:
                    incoming[e.to_route_id] += 1

            # Start node: explicit active_route_id, else node with no incoming, else first route.
            start_id = self.active_route_id if self.active_route_id in routes_by_id else None
            if start_id is None:
                roots = [rid for rid, deg in incoming.items() if deg == 0]
                start_id = roots[0] if roots else self.routes[0].id

            decisions_by_from: dict[UUID, Decision] = {}
            for d in self.decisions:
                if d.from_route_id:
                    decisions_by_from[d.from_route_id] = d

            path: list[Route] = []
            visited: set[UUID] = set()
            current = start_id

            # "branching depth" is a soft guard: count how often we take a decision.
            decision_hops = 0
            for _ in range(0, 50):
                node = routes_by_id.get(current)
                if not node:
                    break
                path.append(node)
                if current in visited:
                    break
                visited.add(current)

                next_candidates = [nid for nid in outgoing.get(current, []) if nid in routes_by_id]
                if not next_candidates:
                    break

                d = decisions_by_from.get(current)
                if d and d.options:
                    decision_hops += 1
                    if decision_hops > 10:
                        break
                    chosen = d.chosen_option_id or d.options[0].id
                    next_id: UUID | None = None
                    for opt in d.options:
                        if opt.id == chosen:
                            next_id = opt.route_id
                            break
                    if next_id and next_id in next_candidates:
                        current = next_id
                        continue

                # No decision / invalid choice: if only one edge, follow; else pick the first.
                current = next_candidates[0]

            return path

        # Legacy: phase-based trunk + optional branch per phase.
        trunks: dict[int, Route] = {}
        branches: dict[tuple[int, UUID], Route] = {}
        max_phase = 0
        for r in self.routes:
            max_phase = max(max_phase, int(r.phase))
            if r.kind == RouteKind.trunk:
                trunks[int(r.phase)] = r
            else:
                branches[(int(r.phase), r.id)] = r

        decisions_by_phase: dict[int, Decision] = {}
        for d in self.decisions:
            decisions_by_phase[int(d.phase)] = d

        path: list[Route] = []
        for phase in range(0, max_phase + 1):
            trunk = trunks.get(phase)
            if trunk:
                path.append(trunk)

            d = decisions_by_phase.get(phase)
            if not d:
                continue

            chosen = d.chosen_option_id or (d.options[0].id if d.options else None)
            if not chosen:
                continue
            chosen_route_id: UUID | None = None
            for opt in d.options:
                if opt.id == chosen:
                    chosen_route_id = opt.route_id
                    break
            if chosen_route_id:
                br = branches.get((phase, chosen_route_id))
                if br:
                    path.append(br)

        return path

    def selected_route(self) -> Route | None:
        """Return the currently selected (branch) route.

        Backwards-compatible helper for UI/tests that expect exactly one active route.
        For multi-switch plans, this returns the chosen branch of the first decision when present,
        otherwise falls back to active_route_id or the first route.
        """

        if not self.routes:
            return None

        # If this is a graph plan, the "selected" route is the current node in the active path.
        if self.edges:
            path = self.selected_path_routes()
            return path[-1] if path else self.routes[0]

        # Legacy: prefer first decision choice (if it exists)
        if self.decisions:
            d = self.decisions[0]
            chosen = d.chosen_option_id or (d.options[0].id if d.options else None)
            if chosen:
                for opt in d.options:
                    if opt.id == chosen:
                        for r in self.routes:
                            if r.id == opt.route_id:
                                return r

        if self.active_route_id:
            for r in self.routes:
                if r.id == self.active_route_id:
                    return r

        return self.routes[0]
