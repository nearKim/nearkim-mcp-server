from abc import ABC, abstractmethod


class TodoistPort(ABC):
    @abstractmethod
    async def get_task(self, task_id: str) -> dict: ...

    @abstractmethod
    async def apply_eisenhower(self, task_id: str, decision) -> None: ...

    @abstractmethod
    async def should_ignore_task(self, task_json: dict) -> bool: ...
