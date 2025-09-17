from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from src.application.dto.webhook import WebhookEventDTO, WebhookResponseDTO
from src.application.middleware.base import MiddlewarePipeline
from src.application.commands.classification import ClassifyTaskCommand
from src.application.middleware.classification import (
    ClassificationHandler,
    FallbackMiddleware,
    ForcedJsonMiddleware,
    LoggingMiddleware,
)
from src.domain.exceptions import WebhookValidationException
from src.domain.models import DecisionRecord
from src.domain.repositories import DecisionRepository
from src.domain.services.classification import ClassifierService
from src.ports.todoist import TodoistPort


class TodoistWebhookService:
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
        self.decisions = decisions
        self.output_mode = output_mode
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        
        handler = ClassificationHandler(classifier)
        self.classification_pipeline = (
            MiddlewarePipeline(handler)
            .use(FallbackMiddleware())
            .use(LoggingMiddleware())
            .use(ForcedJsonMiddleware())
        )

    async def handle(
        self, event_name: str, payload: Dict[str, Any]
    ) -> WebhookResponseDTO:
        try:
            event = WebhookEventDTO.from_payload(event_name, payload)
        except ValueError as e:
            raise WebhookValidationException(str(e))
        
        if event.event_name in self.CLASSIFY_EVENTS:
            return await self._handle_classification(event)
        if event.event_name in self.COMPLETE_EVENTS:
            return await self._handle_completion(event)
        
        return WebhookResponseDTO.unsupported_event(event.event_name)

    async def _handle_classification(
        self, event: WebhookEventDTO
    ) -> WebhookResponseDTO:
        task_id = event.task_id
        task = await self.todoist_port.get_task(task_id)

        if await self.todoist_port.should_ignore_task(task):
            await self.decisions.delete(task_id)
            return WebhookResponseDTO.ignored(task_id, event.event_name)

        command = ClassifyTaskCommand(task)
        decision = await self.classification_pipeline.execute(command)

        await self.todoist_port.apply_eisenhower(task_id, decision)

        record = DecisionRecord.from_decision(
            todoist_id=task_id,
            decision=decision,
            applied_mode=self.output_mode,  # type: ignore[arg-type]
            updated_at=self._clock(),
        )
        await self.decisions.save(record)

        return WebhookResponseDTO.applied(task_id, event.event_name, decision)

    async def _handle_completion(
        self, event: WebhookEventDTO
    ) -> WebhookResponseDTO:
        await self.decisions.delete(event.task_id)
        return WebhookResponseDTO.completed(event.task_id, event.event_name)



