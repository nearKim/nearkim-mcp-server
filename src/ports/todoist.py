from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.entities import Task
    from src.domain.models import ClassificationDecision


class TodoistPort(ABC):
    @abstractmethod
    async def get_task(self, task_id: str) -> "Task": ...

    @abstractmethod
    async def apply_eisenhower(self, task_id: str, decision: "ClassificationDecision") -> None: ...

    @abstractmethod
    async def should_ignore_task(self, task: "Task") -> bool: ...
