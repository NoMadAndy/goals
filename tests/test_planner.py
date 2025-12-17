from stellwerk.planner import PlanRequest, heuristic_plan


def test_heuristic_plan_is_deterministic():
    req = PlanRequest(raw_goal="Mehr Sport", context="3x pro Woche")
    a = heuristic_plan(req)
    b = heuristic_plan(req)

    assert a.title == b.title
    assert a.description == b.description
    assert len(a.routes) == len(b.routes)
    assert len(a.decisions) == len(b.decisions)

    assert a.prologue == b.prologue
    assert a.rallying_cry == b.rallying_cry

    for ra, rb in zip(a.routes, b.routes, strict=True):
        assert ra.title == rb.title
        assert ra.description == rb.description
        assert len(ra.tasks) == len(rb.tasks)

        for ta, tb in zip(ra.tasks, rb.tasks, strict=True):
            assert ta.title == tb.title
            assert ta.notes == tb.notes
            assert len(ta.work_packages) == len(tb.work_packages)

            for wpa, wpb in zip(ta.work_packages, tb.work_packages, strict=True):
                assert wpa.title == wpb.title
                assert wpa.notes == wpb.notes
                assert wpa.length == wpb.length
                assert wpa.grade == wpb.grade


def test_heuristic_plan_has_lengths_and_grades_in_bounds():
    goal = heuristic_plan(PlanRequest(raw_goal="Projekt abschließen"))
    assert 2 <= len(goal.routes) <= 3

    for route in goal.routes:
        assert 5 <= len(route.tasks) <= 9

        for task in route.tasks:
            assert 3 <= len(task.work_packages) <= 8
            for wp in task.work_packages:
                assert 1 <= wp.length <= 8
                assert 0 <= wp.grade <= 10
