from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .entities import Task
from .models import ClassificationDecision, DecisionRecord, Quadrant


class TasksRepo(ABC):
    @abstractmethod
    async def get_by_todoist_id(self, todoist_id: str) -> Task: ...

    @abstractmethod
    async def upsert_from_todoist_json(self, data: dict) -> Task: ...

    @abstractmethod
    async def mark_done_or_remove(self, todoist_id: str) -> None: ...


class DecisionRepository(ABC):
    @abstractmethod
    async def save(self, record: DecisionRecord) -> None: ...

    @abstractmethod
    async def delete(self, todoist_id: str) -> None: ...

    @abstractmethod
    async def get(self, todoist_id: str) -> Optional[DecisionRecord]: ...
    
    @abstractmethod
    async def save_decision(self, task_id: str, decision: ClassificationDecision) -> None: ...
    
    @abstractmethod
    async def get_quadrant_breakdown(self) -> Dict[str, Any]: ...
    
    @abstractmethod
    async def get_recent_decisions(self, limit: int = 10) -> List[DecisionRecord]: ...
    
    @abstractmethod
    async def get_by_quadrant(self, quadrant: Quadrant) -> List[DecisionRecord]: ...
