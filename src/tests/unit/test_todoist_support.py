from types import SimpleNamespace

from src.adapters.openai.dto import EisenhowerCommandBuilder
from src.adapters.todoist.dto import Priority


def test_priority_from_quadrant_accepts_string_labels():
    assert Priority.from_quadrant("Q1") == Priority.P1
    assert Priority.from_quadrant("q2") == Priority.P2
    assert Priority.from_quadrant("Q3") == Priority.P3
    assert Priority.from_quadrant("Q4") == Priority.P4


def test_priority_from_quadrant_accepts_integers():
    assert Priority.from_quadrant(1) == Priority.P1
    assert Priority.from_quadrant(4) == Priority.P4
    assert Priority.from_quadrant(99) == Priority.P4


def test_eisenhower_builder_appends_force_json_suffix():
    task = SimpleNamespace(content="Draft OKRs", due="2024-04-01")
    builder = EisenhowerCommandBuilder("gpt-test")
    request = builder.with_task_context(
        task, {"role": "PM"}, {}, force_json=True
    ).build()
    user_message = request.input[-1].content
    assert user_message.endswith("Return strict JSON only.")
