from datetime import datetime, timezone
from typing import Any

import pytest

from src.application.service.webhook import TodoistWebhookService
from src.adapters.memory_cache import InMemoryDecisionRepository
from src.domain.entities import Task
from src.domain.exceptions import LLMResponseFormatError
from src.domain.models import ClassificationDecision, DecisionRecord
from src.ports.todoist import TodoistPort


class FakeTodoistPort(TodoistPort):
    def __init__(self, task: dict[str, Any], ignore: bool = False):
        self._task = task
        self._ignore = ignore
        self.applied: list[tuple[str, ClassificationDecision]] = []
        self.fetch_count = 0
        self.last_ignore_payload: dict[str, Any] | None = None

    async def get_task(self, task_id: str) -> dict:
        self.fetch_count += 1
        return self._task

    async def apply_eisenhower(self, task_id: str, decision) -> None:
        self.applied.append((task_id, decision))

    async def should_ignore_task(self, task_json: dict) -> bool:
        self.last_ignore_payload = task_json
        return self._ignore


class FakeClassifier:
    def __init__(self, decision: ClassificationDecision):
        self.decision = decision
        self.calls: list[bool] = []

    def classify(
        self, task: Task, *, force_json: bool = False
    ) -> ClassificationDecision:
        self.calls.append(force_json)
        return self.decision


class RetryClassifier:
    def __init__(self, decision: ClassificationDecision, fail_first: bool = True):
        self.decision = decision
        self.fail_first = fail_first
        self.calls: list[bool] = []

    def classify(
        self, task: Task, *, force_json: bool = False
    ) -> ClassificationDecision:
        self.calls.append(force_json)
        if self.fail_first and not force_json:
            raise LLMResponseFormatError("invalid json")
        if self.fail_first and force_json:
            return self.decision
        raise LLMResponseFormatError("still invalid")


@pytest.fixture
def canonical_task() -> dict[str, Any]:
    return {
        "id": "123",
        "content": "Prepare quarterly planning deck",
        "labels": ["work"],
        "project_id": "42",
        "due": {"date": "2024-03-01"},
    }


@pytest.fixture
def decision() -> ClassificationDecision:
    return ClassificationDecision(
        quadrant="Q2", urgent=False, important=True, reason="Deep work"
    )


@pytest.fixture
def fixed_clock():
    return lambda: datetime(2024, 1, 1, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_webhook_classifies_and_applies_decision(
    canonical_task, decision, fixed_clock
):
    todoist_port = FakeTodoistPort(task=canonical_task)
    classifier = FakeClassifier(decision)
    decisions_repo = InMemoryDecisionRepository()
    service = TodoistWebhookService(
        todoist_port,
        classifier,
        decisions_repo,
        output_mode="labels",
        clock=fixed_clock,
    )

    payload = {"event_name": "item:added", "event_data": {"id": canonical_task["id"]}}
    result = await service.handle("item:added", payload)

    assert result["status"] == "applied"
    assert todoist_port.applied[0][0] == canonical_task["id"]
    saved = await decisions_repo.get(canonical_task["id"])
    assert saved is not None
    assert saved.quadrant == "Q2"
    assert classifier.calls == [False]
    assert todoist_port.last_ignore_payload["id"] == canonical_task["id"]


@pytest.mark.asyncio
async def test_webhook_skips_ignored_tasks(canonical_task, decision, fixed_clock):
    todoist_port = FakeTodoistPort(task=canonical_task, ignore=True)
    classifier = FakeClassifier(decision)
    decisions_repo = InMemoryDecisionRepository()
    service = TodoistWebhookService(
        todoist_port,
        classifier,
        decisions_repo,
        output_mode="labels",
        clock=fixed_clock,
    )

    payload = {"event_name": "item:added", "event_data": {"id": canonical_task["id"]}}
    result = await service.handle("item:added", payload)

    assert result["status"] == "ignored"
    assert not todoist_port.applied
    assert classifier.calls == []
    assert await decisions_repo.get(canonical_task["id"]) is None


@pytest.mark.asyncio
async def test_webhook_retries_on_invalid_json(canonical_task, decision, fixed_clock):
    todoist_port = FakeTodoistPort(task=canonical_task)
    classifier = RetryClassifier(decision, fail_first=True)
    decisions_repo = InMemoryDecisionRepository()
    service = TodoistWebhookService(
        todoist_port,
        classifier,
        decisions_repo,
        output_mode="priorities",
        clock=fixed_clock,
    )

    payload = {"event_name": "item:updated", "event_data": {"id": canonical_task["id"]}}
    result = await service.handle("item:updated", payload)

    assert result["status"] == "applied"
    assert classifier.calls == [False, True]
    saved = await decisions_repo.get(canonical_task["id"])
    assert saved is not None
    assert saved.applied_mode == "priorities"


@pytest.mark.asyncio
async def test_webhook_reports_llm_error_after_second_failure(
    canonical_task, decision, fixed_clock
):
    todoist_port = FakeTodoistPort(task=canonical_task)

    class AlwaysFailClassifier:
        def __init__(self):
            self.calls: list[bool] = []

        def classify(
            self, task: Task, *, force_json: bool = False
        ) -> ClassificationDecision:
            self.calls.append(force_json)
            raise LLMResponseFormatError("invalid json")

    classifier = AlwaysFailClassifier()
    decisions_repo = InMemoryDecisionRepository()
    service = TodoistWebhookService(
        todoist_port,
        classifier,
        decisions_repo,
        output_mode="labels",
        clock=fixed_clock,
    )

    payload = {"event_name": "item:added", "event_data": {"id": canonical_task["id"]}}
    result = await service.handle("item:added", payload)

    assert result["status"] == "llm_error"
    assert classifier.calls == [False, True]
    assert not todoist_port.applied
    assert await decisions_repo.get(canonical_task["id"]) is None


@pytest.mark.asyncio
async def test_completion_event_removes_saved_decision(
    canonical_task, decision, fixed_clock
):
    todoist_port = FakeTodoistPort(task=canonical_task)
    decisions_repo = InMemoryDecisionRepository()
    await decisions_repo.save(
        DecisionRecord.from_decision(
            todoist_id=canonical_task["id"],
            decision=decision,
            applied_mode="labels",
            updated_at=fixed_clock(),
        )
    )

    class NoopClassifier:
        def classify(
            self, task: Task, *, force_json: bool = False
        ) -> ClassificationDecision:
            raise AssertionError(
                "Classifier should not be invoked for completion events"
            )

    service = TodoistWebhookService(
        todoist_port,
        NoopClassifier(),
        decisions_repo,
        output_mode="labels",
        clock=fixed_clock,
    )

    payload = {
        "event_name": "item:completed",
        "event_data": {"id": canonical_task["id"]},
    }
    result = await service.handle("item:completed", payload)

    assert result["status"] == "completed"
    assert await decisions_repo.get(canonical_task["id"]) is None
    assert not todoist_port.applied
