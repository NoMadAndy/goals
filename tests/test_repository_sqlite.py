from sqlalchemy import create_engine

from stellwerk.db import init_db, open_session
from stellwerk.repository import (
    apply_plan,
    create_goal,
    delete_goal,
    get_goal,
    list_goals,
    toggle_work_package,
    update_work_package,
)
from stellwerk.models import Goal, Route, Task, WorkPackage, WorkPackageStatus


def _sample_goal() -> Goal:
    route = Route(
        title="Standard",
        description="",
        tasks=[
            Task(
                title="Aufgabe 1",
                notes="",
                work_packages=[WorkPackage(title="WP 1", notes="", length=2, grade=3)],
            )
        ],
    )
    return Goal(
        title="Mehr Sport",
        description="",
        routes=[route],
        decisions=[],
        people=[],
        active_route_id=route.id,
        prologue="",
        rallying_cry="",
    )


def test_repository_roundtrip_sqlite():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    init_db(engine)

    with open_session(engine) as session:
        goal_id = create_goal(session, title="Mehr Sport", description="")

    with open_session(engine) as session:
        goals = list_goals(session)
        assert len(goals) == 1
        assert goals[0].id == goal_id

    planned = _sample_goal()

    with open_session(engine) as session:
        apply_plan(session, goal_id, planned)

    with open_session(engine) as session:
        goal = get_goal(session, goal_id)
        assert goal is not None
        route = goal.selected_route()
        assert route is not None
        assert len(route.tasks) >= 1
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

    planned = _sample_goal()
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


def test_apply_plan_skips_decision_with_missing_route_fk():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    init_db(engine)

    with open_session(engine) as session:
        goal_id = create_goal(session, title="Ziel", description="")

    route = Route(title="Abschnitt", description="", tasks=[])
    planned = Goal(title="Ziel", description="", routes=[route], decisions=[], people=[])

    # Craft an inconsistent decision referencing a non-existent route id.
    from uuid import uuid4

    from stellwerk.models import Decision, DecisionOption

    planned.decisions = [
        Decision(
            title="Weiche",
            prompt="?",
            from_route_id=uuid4(),
            options=[DecisionOption(label="A", route_id=route.id)],
        )
    ]

    with open_session(engine) as session:
        apply_plan(session, goal_id, planned)

    with open_session(engine) as session:
        goal = get_goal(session, goal_id)
        assert goal is not None
        assert len(goal.routes) == 1
        # Decision should have been skipped rather than violating FK.
        assert len(goal.decisions) == 0


def test_delete_goal_removes_goal_and_children():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    init_db(engine)

    with open_session(engine) as session:
        goal_id = create_goal(session, title="Ziel", description="")

    planned = _sample_goal()
    with open_session(engine) as session:
        apply_plan(session, goal_id, planned)

    with open_session(engine) as session:
        assert get_goal(session, goal_id) is not None

    with open_session(engine) as session:
        delete_goal(session, goal_id)

    with open_session(engine) as session:
        assert get_goal(session, goal_id) is None
        assert list_goals(session) == []
