from stellwerk.planner import PlanRequest, heuristic_plan


def test_heuristic_plan_is_deterministic():
    req = PlanRequest(raw_goal="Mehr Sport", context="3x pro Woche")
    a = heuristic_plan(req)
    b = heuristic_plan(req)

    assert a.title == b.title
    assert a.description == b.description
    assert len(a.tasks) == len(b.tasks)

    assert a.prologue == b.prologue
    assert a.rallying_cry == b.rallying_cry

    for ta, tb in zip(a.tasks, b.tasks, strict=True):
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
    assert 3 <= len(goal.tasks) <= 5

    for task in goal.tasks:
        assert 2 <= len(task.work_packages) <= 4
        for wp in task.work_packages:
            assert 1 <= wp.length <= 5
            assert 0 <= wp.grade <= 10
