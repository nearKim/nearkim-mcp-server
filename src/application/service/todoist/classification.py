"""Classification service for applying Eisenhower matrix decisions."""

from __future__ import annotations

from src.adapters.todoist.dto import Priority
from src.domain.models import ClassificationDecision
from .label import LabelService
from .task import TaskService


class ClassificationService:
    """
    Service for applying Eisenhower matrix classifications to tasks.
    
    Supports applying classifications as either labels or priority levels
    based on configuration.
    """
    
    def __init__(self, task_service: TaskService, label_service: LabelService):
        self.task_service = task_service
        self.label_service = label_service

    async def apply_eisenhower_as_labels(
        self,
        task_id: str,
        decision: ClassificationDecision,
        urgent_label: str,
        important_label: str,
    ) -> None:
        """
        Apply Eisenhower classification as task labels.
        
        Args:
            task_id: The ID of the task to classify
            decision: The classification decision
            urgent_label: Label name for urgent tasks
            important_label: Label name for important tasks
        """
        labels = []
        if decision.urgent:
            labels.append(urgent_label)
        if decision.important:
            labels.append(important_label)
        if labels:
            label_map = await self.label_service.ensure_labels_exist(labels)
            valid_labels = [name for name in labels if name in label_map]
            await self.task_service.merge_and_update_labels(task_id, valid_labels)

    async def apply_eisenhower_as_priority(
        self, task_id: str, decision: ClassificationDecision
    ) -> None:
        """
        Apply Eisenhower classification as task priority.
        
        Maps quadrants to Todoist priority levels:
        - Q1 (Urgent & Important): P1
        - Q2 (Important, Not Urgent): P2  
        - Q3 (Urgent, Not Important): P3
        - Q4 (Not Urgent, Not Important): P4
        """
        priority = Priority.from_quadrant(decision.quadrant)
        await self.task_service.set_priority(task_id, priority.value)