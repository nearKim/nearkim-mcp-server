from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, List, Optional, Any

if TYPE_CHECKING:
    from src.domain.entities import Task
    from src.domain.models import ClassificationDecision


class TodoistPort(ABC):
    
    @abstractmethod
    async def get_task(self, task_id: str) -> "Task":
        ...

    @abstractmethod
    async def fetch_tasks(self, project_id: Optional[str] = None, filter_str: Optional[str] = None) -> List["Task"]:
        ...
    
    @abstractmethod
    async def create_task(self, content: str, **kwargs) -> "Task":
        ...
    
    @abstractmethod
    async def update_task(self, task_id: str, **updates) -> "Task":
        ...
    
    @abstractmethod
    async def delete_task(self, task_id: str) -> bool:
        ...
    
    @abstractmethod
    async def complete_task(self, task_id: str) -> bool:
        ...
    @abstractmethod
    async def apply_eisenhower(self, task_id: str, decision: "ClassificationDecision") -> None:
        ...
    
    @abstractmethod
    async def remove_eisenhower_labels(self, task_id: str) -> None:
        ...
    @abstractmethod
    async def add_labels(self, task_id: str, labels: List[str]) -> None:
        ...
    
    @abstractmethod
    async def remove_labels(self, task_id: str, labels: List[str]) -> None:
        ...
    
    @abstractmethod
    async def ensure_label_exists(self, label_name: str) -> str:
        ...
    @abstractmethod
    async def set_priority(self, task_id: str, priority: int) -> None:
        ...
    @abstractmethod
    async def should_ignore_task(self, task: "Task") -> bool:
        ...
    
    @abstractmethod
    async def set_manual_override(self, task_id: str, override: bool) -> None:
        ...
    @abstractmethod
    async def get_projects(self) -> List[Dict[str, Any]]:
        ...
    
    @abstractmethod
    async def get_project(self, project_id: str) -> Dict[str, Any]:
        ...
    @abstractmethod
    async def add_comment(self, task_id: str, content: str) -> None:
        ...
    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        ...
