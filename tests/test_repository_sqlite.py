from sqlalchemy import create_engine

from stellwerk.db import init_db, open_session
from stellwerk.planner import PlanRequest, heuristic_plan
from stellwerk.repository import (
    apply_plan,
    create_goal,
    get_goal,
    list_goals,
    toggle_work_package,
    update_work_package,
)
from stellwerk.models import WorkPackageStatus


def test_repository_roundtrip_sqlite():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    init_db(engine)

    with open_session(engine) as session:
        goal_id = create_goal(session, title="Mehr Sport", description="")

    with open_session(engine) as session:
        goals = list_goals(session)
        assert len(goals) == 1
        assert goals[0].id == goal_id

    planned = heuristic_plan(PlanRequest(raw_goal="Mehr Sport", context="3x pro Woche"))

    with open_session(engine) as session:
        apply_plan(session, goal_id, planned)

    with open_session(engine) as session:
        goal = get_goal(session, goal_id)
        assert goal is not None
        route = goal.selected_route()
        assert route is not None
        assert len(route.tasks) >= 5
        first_wp = route.tasks[0].work_packages[0]

    with open_session(engine) as session:
        toggle_work_package(session, first_wp.id)

    with open_session(engine) as session:
        goal2 = get_goal(session, goal_id)
        assert goal2 is not None
        route2 = goal2.selected_route()
        assert route2 is not None
        wp2 = route2.tasks[0].work_packages[0]
        assert wp2.status.value == "done"


def test_update_work_package_persists_notes_and_status():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    init_db(engine)

    with open_session(engine) as session:
        goal_id = create_goal(session, title="Ziel", description="")

    planned = heuristic_plan(PlanRequest(raw_goal="Ziel"))
    with open_session(engine) as session:
        apply_plan(session, goal_id, planned)

    with open_session(engine) as session:
        goal = get_goal(session, goal_id)
        assert goal is not None
        route = goal.selected_route()
        assert route is not None
        wp = route.tasks[0].work_packages[0]

    with open_session(engine) as session:
        update_work_package(
            session,
            wp.id,
            title="Neuer Titel",
            notes="Definition of Done: fertig.",
            length=3,
            grade=7,
            status=WorkPackageStatus.diverted,
        )

    with open_session(engine) as session:
        goal2 = get_goal(session, goal_id)
        assert goal2 is not None
        route2 = goal2.selected_route()
        assert route2 is not None
        wp2 = route2.tasks[0].work_packages[0]
        assert wp2.title == "Neuer Titel"
        assert wp2.notes == "Definition of Done: fertig."
        assert wp2.length == 3
        assert wp2.grade == 7
        assert wp2.status.value == "diverted"
