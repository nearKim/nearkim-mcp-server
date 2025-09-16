from abc import ABC, abstractmethod

from .entities import Task
from .models import DecisionRecord


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
    async def get(self, todoist_id: str) -> DecisionRecord | None: ...
