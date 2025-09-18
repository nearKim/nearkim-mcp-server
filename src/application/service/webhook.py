from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from src.application.dto.webhook import WebhookEventDTO, WebhookResponseDTO
from src.application.middleware.base import MiddlewarePipeline
from src.application.commands.classification import ClassifyTaskCommand
from src.application.middleware.classification import (
    ClassificationHandler,
    ForcedJsonMiddleware,
    LoggingMiddleware,
)
from src.application.middleware.error_handling import ErrorHandlingMiddleware
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
        email_service=None,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.todoist_port = todoist_port
        self.decisions = decisions
        self.output_mode = output_mode
        self.email_service = email_service
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        
        handler = ClassificationHandler(classifier)
        self.classification_pipeline = (
            MiddlewarePipeline(handler)
            .use(ErrorHandlingMiddleware(
                todoist_adapter=todoist_port,
                email_service=email_service,
                error_label="error"
            ))
            .use(LoggingMiddleware())
            .use(ForcedJsonMiddleware())
        )

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature using HMAC.
        
        Args:
            payload: Raw request body bytes
            signature: X-Todoist-Hmac-SHA256 header value
            
        Returns:
            True if signature is valid, False otherwise
        """
        return self.todoist_port.verify_webhook_signature(payload, signature)
    
    async def handle(
        self, event_name: str, payload: Dict[str, Any], 
        raw_payload: Optional[bytes] = None, signature: Optional[str] = None
    ) -> WebhookResponseDTO:
        """Handle webhook event with optional HMAC verification.
        
        Args:
            event_name: Event type (e.g., 'item:added')
            payload: Parsed JSON payload
            raw_payload: Raw request body for signature verification
            signature: HMAC signature from X-Todoist-Hmac-SHA256 header
            
        Returns:
            WebhookResponseDTO with processing result
            
        Raises:
            WebhookValidationException: If signature verification fails
        """
        # Verify signature if provided
        if raw_payload and signature:
            if not self.verify_signature(raw_payload, signature):
                raise WebhookValidationException("Invalid webhook signature")
        
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



