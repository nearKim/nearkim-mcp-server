from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Task:
    todoist_id: str
    content: str
    description: Optional[str] = None
    due: Optional[Dict[str, Any]] = None
    labels: List[str] = field(default_factory=list)
    project_id: Optional[str] = None
    priority: Optional[int] = None

    @classmethod
    def from_todoist_json(cls, data: dict) -> "Task":
        """Create a :class:`Task` from the canonical Todoist task payload."""

        if "id" not in data:
            raise ValueError("Todoist task JSON must include an 'id' field")

        task = cls(
            todoist_id=str(data["id"]),
            content=data.get("content", ""),
            description=data.get("description"),
            due=data.get("due"),
            labels=list(data.get("labels", []) or []),
            project_id=data.get("project_id"),
            priority=data.get("priority"),
        )
        return task

    def due_iso(self) -> Optional[str]:
        """Return the due datetime in ISO format when available."""

        if not self.due:
            return None
        due_datetime = self.due.get("datetime") if isinstance(self.due, dict) else None
        if isinstance(due_datetime, datetime):
            return due_datetime.isoformat()
        if isinstance(due_datetime, str):
            return due_datetime
        return self.due.get("date") if isinstance(self.due, dict) else None
