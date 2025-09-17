
from __future__ import annotations

from src.adapters.todoist.dto import TaskDTO, TaskUpdateDTO
from .api import TodoistAPIBase


class TaskService:
    
    def __init__(self, api: TodoistAPIBase):
        self.api = api

    async def get_task(self, task_id: str) -> TaskDTO:
        return await self.api.get_task(task_id)

    async def update_task(self, task_id: str, update: TaskUpdateDTO) -> None:
        params = update.to_api_params()
        if params:
            await self.api.update_task(task_id, **params)

    async def set_priority(self, task_id: str, priority: int) -> None:
        update = TaskUpdateDTO(priority=priority)
        await self.update_task(task_id, update)

    async def merge_and_update_labels(
        self, task_id: str, label_names: list[str]
    ) -> None:
        if not label_names:
            return
        task = await self.get_task(task_id)
        current_labels = set(task.labels)
        new_labels = {name.lstrip("@") for name in label_names}
        merged_labels = list(current_labels | new_labels)
        if merged_labels != task.labels:
            update = TaskUpdateDTO(labels=merged_labels)
            await self.update_task(task_id, update)