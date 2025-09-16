from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

from src.domain.entities import Task
from src.domain.exceptions import LLMResponseFormatError
from src.domain.models import ClassificationDecision, DecisionRecord
from src.domain.repositories import DecisionRepository
from src.domain.services import ClassifierService
from src.ports.todoist import TodoistPort


class TodoistWebhookService:
    """Coordinate Todoist webhook processing and Eisenhower classification."""

    CLASSIFY_EVENTS = {"item:added", "item:updated", "item:uncompleted"}
    COMPLETE_EVENTS = {"item:completed", "item:deleted"}

    def __init__(
        self,
        todoist_port: TodoistPort,
        classifier: ClassifierService,
        decisions: DecisionRepository,
        *,
        output_mode: str,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.todoist_port = todoist_port
        self.classifier = classifier
        self.decisions = decisions
        self.output_mode = output_mode
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def handle(
        self, event_name: str, payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        normalized = event_name or payload.get("event_name")
        if not normalized:
            raise ValueError("Event name is required for webhook handling")

        if normalized in self.CLASSIFY_EVENTS:
            return await self._handle_classification(normalized, payload)
        if normalized in self.COMPLETE_EVENTS:
            return await self._handle_completion(normalized, payload)
        return {
            "status": "ignored",
            "event": normalized,
            "reason": "unsupported_event",
        }

    async def _handle_classification(
        self, event_name: str, payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        task_id = self._extract_task_id(payload)
        canonical = await self.todoist_port.get_task(task_id)
        canonical_dict = self._to_dict(canonical)

        if await self.todoist_port.should_ignore_task(canonical_dict):
            await self.decisions.delete(task_id)
            return {"status": "ignored", "task_id": task_id, "event": event_name}

        task = Task.from_todoist_json(canonical_dict)

        decision = self._classify_with_retry(task)
        if decision is None:
            return {"status": "llm_error", "task_id": task_id, "event": event_name}

        await self.todoist_port.apply_eisenhower(task_id, decision)

        record = DecisionRecord.from_decision(
            todoist_id=task.todoist_id,
            decision=decision,
            applied_mode=self.output_mode,  # type: ignore[arg-type]
            updated_at=self._clock(),
        )
        await self.decisions.save(record)

        return {
            "status": "applied",
            "task_id": task_id,
            "event": event_name,
            "decision": asdict(decision),
        }

    async def _handle_completion(
        self, event_name: str, payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        task_id = self._extract_task_id(payload)
        await self.decisions.delete(task_id)
        return {"status": "completed", "task_id": task_id, "event": event_name}

    def _classify_with_retry(self, task: Task) -> ClassificationDecision | None:
        try:
            return self.classifier.classify(task)
        except LLMResponseFormatError:
            try:
                return self.classifier.classify(task, force_json=True)
            except LLMResponseFormatError:
                return None

    @staticmethod
    def _extract_task_id(payload: Mapping[str, Any]) -> str:
        candidates = [
            payload.get("event_data"),
            payload.get("data"),
            payload,
        ]
        for candidate in candidates:
            if isinstance(candidate, Mapping) and "id" in candidate:
                return str(candidate["id"])
        raise ValueError("Todoist webhook payload did not contain a task identifier")

    @staticmethod
    def _to_dict(task_obj: Any) -> dict[str, Any]:
        if hasattr(task_obj, "model_dump"):
            return task_obj.model_dump()
        if is_dataclass(task_obj):
            return asdict(task_obj)
        if isinstance(task_obj, Mapping):
            return dict(task_obj)
        raise TypeError("Unsupported task representation returned by Todoist port")
