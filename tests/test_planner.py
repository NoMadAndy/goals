import pytest

from stellwerk.planner import PlanRequest, parse_openai_plan
from stellwerk.models import RouteKind


def test_parse_openai_plan_basic_route_and_decision_mapping():
    parsed = {
        "title": "Mehr Sport",
        "description": "Konkret: 3x pro Woche 30 Minuten bewegen.",
        "prologue": "Kleine Schritte.",
        "rallying_cry": "Heute zählt.",
        "people": [
            {"name": "Alex", "role": "companion", "direction": "with_me", "notes": "Zieht mit."},
        ],
        "routes": [
            {
                "title": "Direkt",
                "description": "Kurz und klar.",
                "tasks": [
                    {
                        "title": "Start",
                        "notes": "",
                        "work_packages": [
                            {"title": "Schuhe bereitstellen", "notes": "", "length": 2, "grade": 1},
                        ],
                    }
                ],
            },
            {
                "title": "Robust",
                "description": "Mit Absicherung.",
                "tasks": [
                    {
                        "title": "Plan",
                        "notes": "",
                        "work_packages": [
                            {"title": "Slots im Kalender", "notes": "", "length": 3, "grade": 2},
                        ],
                    }
                ],
            },
        ],
        "decisions": [
            {
                "title": "Weiche",
                "prompt": "Wähle bewusst.",
                "options": [
                    {"label": "Direkt", "route_index": 0},
                    {"label": "Robust", "route_index": 1},
                ],
                "chosen_option_index": 1,
            }
        ],
    }

    goal = parse_openai_plan(parsed, PlanRequest(raw_goal="Mehr Sport", context="3x/Woche"))

    assert goal.title == "Mehr Sport"
    assert len(goal.routes) == 2
    assert len(goal.decisions) == 1
    assert len(goal.people) == 1

    # chosen_option_index = 1 => active route is routes[1]
    assert goal.active_route_id == goal.routes[1].id
    assert goal.decisions[0].options[0].route_id == goal.routes[0].id
    assert goal.decisions[0].options[1].route_id == goal.routes[1].id


def test_parse_openai_plan_rejects_out_of_bounds_length_and_grade():
    parsed = {
        "title": "Ziel",
        "description": "",
        "routes": [
            {
                "title": "Route",
                "description": "",
                "tasks": [
                    {
                        "title": "Aufgabe",
                        "notes": "",
                        "work_packages": [
                            {"title": "WP", "notes": "", "length": 9, "grade": 11},
                        ],
                    }
                ],
            }
        ],
        "decisions": [],
        "people": [],
    }

    with pytest.raises(ValueError):
        parse_openai_plan(parsed, PlanRequest(raw_goal="Ziel"))


def test_parse_openai_plan_coerces_length_with_units_in_string():
    parsed = {
        "title": "Ziel",
        "description": "",
        "routes": [
            {
                "title": "Route",
                "description": "",
                "tasks": [
                    {
                        "title": "Aufgabe",
                        "notes": "",
                        "work_packages": [
                            {"title": "WP", "notes": "", "length": "30 Minuten", "grade": "2/10"},
                        ],
                    }
                ],
            }
        ],
        "decisions": [],
        "people": [],
    }

    goal = parse_openai_plan(parsed, PlanRequest(raw_goal="Ziel"))
    wp = goal.routes[0].tasks[0].work_packages[0]
    assert 1 <= wp.length <= 8
    assert 0 <= wp.grade <= 10


def test_parse_openai_plan_phases_schema_creates_trunk_and_branch_routes():
    parsed = {
        "title": "Ziel",
        "description": "",
        "prologue": "",
        "rallying_cry": "",
        "people": [],
        "phases": [
            {
                "phase": 0,
                "trunk": {
                    "title": "Abschnitt 1",
                    "description": "",
                    "tasks": [
                        {
                            "title": "A",
                            "notes": "",
                            "work_packages": [
                                {"title": "WP", "notes": "", "length": 2, "grade": 3}
                            ],
                        }
                    ],
                },
                "decision": {
                    "title": "Weiche",
                    "prompt": "",
                    "options": [
                        {
                            "label": "Option 1",
                            "branch": {
                                "title": "Abzweig 1",
                                "description": "",
                                "tasks": [
                                    {
                                        "title": "B",
                                        "notes": "",
                                        "work_packages": [
                                            {"title": "WP", "notes": "", "length": 1, "grade": 0}
                                        ],
                                    }
                                ],
                            },
                        }
                    ],
                    "chosen_option_index": 0,
                },
            },
            {
                "phase": 1,
                "trunk": {
                    "title": "Abschnitt 2",
                    "description": "",
                    "tasks": [
                        {
                            "title": "C",
                            "notes": "",
                            "work_packages": [
                                {"title": "WP", "notes": "", "length": 2, "grade": 1}
                            ],
                        }
                    ],
                },
            },
        ],
    }

    goal = parse_openai_plan(parsed, PlanRequest(raw_goal="Ziel"))

    assert any(r.kind == RouteKind.trunk and r.phase == 0 for r in goal.routes)
    assert any(r.kind == RouteKind.branch and r.phase == 0 for r in goal.routes)
    assert any(r.kind == RouteKind.trunk and r.phase == 1 for r in goal.routes)
    assert len(goal.decisions) == 1
    assert goal.decisions[0].phase == 0


def test_parse_openai_plan_graph_schema_creates_edges_and_node_attached_decisions():
    parsed = {
        "title": "Ziel",
        "description": "",
        "prologue": "",
        "rallying_cry": "",
        "people": [],
        "routes": [
            {
                "id": "r0",
                "title": "Start",
                "description": "",
                "kind": "trunk",
                "phase": 0,
                "tasks": [
                    {
                        "title": "A",
                        "notes": "",
                        "work_packages": [
                            {
                                "title": "WP",
                                "notes": "## Schritte\n- Test\n\n## Quellen\n- https://example.com",
                                "length": 2,
                                "grade": 3,
                            }
                        ],
                    }
                ],
            },
            {
                "id": "r1",
                "title": "Variante 1",
                "description": "",
                "kind": "branch",
                "phase": 1,
                "tasks": [
                    {
                        "title": "B",
                        "notes": "",
                        "work_packages": [{"title": "WP", "notes": "x", "length": 1, "grade": 0}],
                    }
                ],
            },
            {
                "id": "r2",
                "title": "Variante 2",
                "description": "",
                "kind": "branch",
                "phase": 1,
                "tasks": [
                    {
                        "title": "C",
                        "notes": "",
                        "work_packages": [{"title": "WP", "notes": "x", "length": 1, "grade": 0}],
                    }
                ],
            },
            {
                "id": "r3",
                "title": "Merge",
                "description": "",
                "kind": "trunk",
                "phase": 2,
                "tasks": [
                    {
                        "title": "D",
                        "notes": "",
                        "work_packages": [{"title": "WP", "notes": "x", "length": 1, "grade": 0}],
                    }
                ],
            },
        ],
        "edges": [
            {"from": "r0", "to": "r1"},
            {"from": "r0", "to": "r2"},
            {"from": "r1", "to": "r3"},
            {"from": "r2", "to": "r3"},
        ],
        "decisions": [
            {
                "title": "Weiche",
                "prompt": "",
                "from": "r0",
                "phase": 0,
                "options": [
                    {"label": "V1", "to": "r1"},
                    {"label": "V2", "to": "r2"},
                ],
                "chosen_option_index": 0,
            }
        ],
    }

    goal = parse_openai_plan(parsed, PlanRequest(raw_goal="Ziel"))

    assert len(goal.routes) == 4
    assert len(goal.edges) == 4
    assert len(goal.decisions) == 1

    # Root is r0 (no incoming edges)
    start = next(r for r in goal.routes if r.title == "Start")
    assert goal.active_route_id == start.id

    assert goal.decisions[0].from_route_id == start.id
    path = goal.selected_path_routes()
    assert [r.title for r in path] == ["Start", "Variante 1", "Merge"]


def test_parse_openai_plan_graph_schema_adds_edges_implied_by_decisions():
    parsed = {
        "title": "Ziel",
        "description": "",
        "prologue": "",
        "rallying_cry": "",
        "people": [],
        "routes": [
            {
                "id": "r0",
                "title": "Start",
                "description": "",
                "kind": "trunk",
                "phase": 0,
                "tasks": [],
            },
            {
                "id": "r1",
                "title": "Option A",
                "description": "",
                "kind": "branch",
                "phase": 1,
                "tasks": [],
            },
            {
                "id": "r2",
                "title": "Option B",
                "description": "",
                "kind": "branch",
                "phase": 1,
                "tasks": [],
            },
        ],
        # Missing edge r0->r2 on purpose.
        "edges": [{"from": "r0", "to": "r1"}],
        "decisions": [
            {
                "title": "Weiche",
                "prompt": "",
                "from": "r0",
                "phase": 0,
                "options": [
                    {"label": "A", "to": "r1"},
                    {"label": "B", "to": "r2"},
                ],
                "chosen_option_index": 0,
            }
        ],
    }

    goal = parse_openai_plan(parsed, PlanRequest(raw_goal="Ziel"))

    start = next(r for r in goal.routes if r.title == "Start")
    opt_b = next(r for r in goal.routes if r.title == "Option B")
    assert any(e.from_route_id == start.id and e.to_route_id == opt_b.id for e in goal.edges)
