from __future__ import annotations

import logging

from src.application.commands.classification import ClassifyTaskCommand
from src.application.middleware.base import Handler, Middleware
from src.domain.exceptions import ClassificationException, LLMResponseFormatError
from src.domain.models import ClassificationDecision, DecisionStatus

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(Middleware[ClassifyTaskCommand, ClassificationDecision]):
    
    def __init__(
        self, 
        todoist_adapter=None,
        email_service=None,
        error_label: str = "error"
    ):
        self.todoist_adapter = todoist_adapter
        self.email_service = email_service
        self.error_label = error_label
    
    async def __call__(
        self,
        command: ClassifyTaskCommand,
        next_handler: Handler[ClassifyTaskCommand, ClassificationDecision]
    ) -> ClassificationDecision:
        try:
            return await next_handler(command)
        except (ClassificationException, LLMResponseFormatError, Exception) as e:
            task = command.task
            error_type = type(e).__name__
            error_msg = str(e)
            
            logger.error(
                f"Classification failed for task {task.todoist_id}: {error_type}: {error_msg}",
                exc_info=e
            )
            
            if self.todoist_adapter:
                try:
                    await self._apply_error_label(task.todoist_id)
                except Exception as label_error:
                    logger.error(f"Failed to apply error label: {label_error}")
            
            if self.email_service:
                try:
                    await self.email_service.send_error_notification(
                        task_id=task.todoist_id,
                        task_content=task.content,
                        error=e,
                        error_detail=f"Classification attempt failed during {error_type}"
                    )
                except Exception as email_error:
                    logger.error(f"Failed to send error notification: {email_error}")
            
            return ClassificationDecision(
                quadrant="Q4",
                urgent=False, 
                important=False,
                reason="Classification failed - marked for manual review",
                status=DecisionStatus.ERROR,
                error_detail=f"{error_type}: {error_msg}"
            )
    
    async def _apply_error_label(self, task_id: str) -> None:
        task_dto = await self.todoist_adapter.get_task(task_id)
        
        if self.error_label not in task_dto.labels:
            task_dto.labels.append(self.error_label)
            await self.todoist_adapter.update_task(
                task_id,
                labels=task_dto.labels
            )
            logger.info(f"Applied '{self.error_label}' label to task {task_id}")