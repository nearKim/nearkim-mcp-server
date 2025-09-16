from abc import ABC, abstractmethod

from .entities import Task


class TasksRepo(ABC):
    @abstractmethod
    async def get_by_todoist_id(self, todoist_id: str) -> Task:
        ...

    @abstractmethod
    async def upsert_from_todoist_json(self, data: dict) -> Task:
        ...

    @abstractmethod
    async def mark_done_or_remove(self, todoist_id: str) -> None:
        ...
