
from __future__ import annotations

from abc import ABC, abstractmethod

from src.adapters.todoist.dto import LabelDTO, ProjectDTO, TaskDTO


class TodoistAPIBase(ABC):
    
    @abstractmethod
    async def get_task(self, task_id: str) -> TaskDTO:
        pass

    @abstractmethod
    async def update_task(self, task_id: str, **params) -> None:
        pass

    @abstractmethod
    async def add_label(self, name: str) -> LabelDTO:
        pass

    @abstractmethod
    async def fetch_labels(self) -> list[LabelDTO]:
        pass

    @abstractmethod
    async def fetch_projects(self) -> list[ProjectDTO]:
        pass