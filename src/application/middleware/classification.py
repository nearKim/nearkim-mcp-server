from __future__ import annotations

from typing import Callable, Optional

from src.application.commands.classification import ClassifyTaskCommand
from src.application.middleware.base import Handler, Middleware
from src.domain.exceptions import ClassificationException, LLMResponseFormatError
from src.domain.models import ClassificationDecision, Quadrant
from src.domain.services.classification import ClassifierService


class ForcedJsonMiddleware(Middleware[ClassifyTaskCommand, ClassificationDecision]):
    async def __call__(
        self, 
        command: ClassifyTaskCommand, 
        next_handler: Handler[ClassifyTaskCommand, ClassificationDecision]
    ) -> ClassificationDecision:
        try:
            return await next_handler(command)
        except LLMResponseFormatError:
            command.force_json = True
            return await next_handler(command)


class LoggingMiddleware(Middleware[ClassifyTaskCommand, ClassificationDecision]):
    def __init__(self, logger: Optional[Callable[[str], None]] = None):
        self.logger = logger or print
    
    async def __call__(
        self,
        command: ClassifyTaskCommand,
        next_handler: Handler[ClassifyTaskCommand, ClassificationDecision]
    ) -> ClassificationDecision:
        self.logger(f"Classifying task: {command.task.todoist_id}")
        try:
            result = await next_handler(command)
            self.logger(f"Classification successful: {result.quadrant}")
            return result
        except Exception as e:
            self.logger(f"Classification failed: {e}")
            raise


class FallbackMiddleware(Middleware[ClassifyTaskCommand, ClassificationDecision]):
    DEFAULT_QUADRANT: Quadrant = "Q4"
    
    async def __call__(
        self,
        command: ClassifyTaskCommand,
        next_handler: Handler[ClassifyTaskCommand, ClassificationDecision]
    ) -> ClassificationDecision:
        try:
            return await next_handler(command)
        except (ClassificationException, LLMResponseFormatError) as e:
            return ClassificationDecision.create_fallback(
                error=e,
                default_quadrant=self.DEFAULT_QUADRANT
            )
        except Exception as e:
            return ClassificationDecision.create_fallback(
                error=Exception(f"Unexpected error during classification: {e}"),
                default_quadrant=self.DEFAULT_QUADRANT
            )


class ClassificationHandler:
    def __init__(self, classifier: ClassifierService):
        self.classifier = classifier
    
    async def __call__(self, command: ClassifyTaskCommand) -> ClassificationDecision:
        return self.classifier.classify(
            command.task,
            force_json=command.force_json
        )