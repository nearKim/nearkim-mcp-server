
from __future__ import annotations

from src.adapters.todoist.dto import Priority
from src.domain.models import ClassificationDecision
from .label import LabelService
from .task import TaskService


class ClassificationService:
    
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
        priority = Priority.from_quadrant(decision.quadrant)
        await self.task_service.set_priority(task_id, priority.value)