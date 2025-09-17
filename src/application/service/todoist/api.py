"""Abstract base class for Todoist API operations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.adapters.todoist.dto import LabelDTO, ProjectDTO, TaskDTO


class TodoistAPIBase(ABC):
    """
    Abstract base class defining the interface for Todoist API operations.
    
    This ABC ensures all Todoist API implementations provide the required
    methods for task, label, and project operations.
    """
    
    @abstractmethod
    async def get_task(self, task_id: str) -> TaskDTO:
        """Retrieve a task by its ID."""
        pass

    @abstractmethod
    async def update_task(self, task_id: str, **params) -> None:
        """Update a task with the given parameters."""
        pass

    @abstractmethod
    async def add_label(self, name: str) -> LabelDTO:
        """Create a new label with the given name."""
        pass

    @abstractmethod
    async def fetch_labels(self) -> list[LabelDTO]:
        """Fetch all labels from Todoist."""
        pass

    @abstractmethod
    async def fetch_projects(self) -> list[ProjectDTO]:
        """Fetch all projects from Todoist."""
        pass