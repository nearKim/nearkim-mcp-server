from typing import Any, Dict

from src.domain.entities import Task


def task_from_dict(task_data: Dict[str, Any]) -> Task:
    labels = task_data.get("labels", [])
    if labels is None:
        labels = []
    
    task_id = task_data.get("id", "")
    if task_id and not isinstance(task_id, str):
        task_id = str(task_id)
    
    return Task(
        todoist_id=task_id,
        content=task_data.get("content", ""),
        project_id=task_data.get("project_id"),
        labels=labels,
        priority=task_data.get("priority", 1),
        due=task_data.get("due")
    )


def task_from_dto(task_dto: Any) -> Task:
    if isinstance(task_dto, dict):
        return task_from_dict(task_dto)
    
    return Task(
        todoist_id=task_dto.id,
        content=task_dto.content,
        project_id=task_dto.project_id,
        labels=task_dto.labels,
        priority=task_dto.priority,
        due=task_dto.due
    )


def task_to_dict(task: Task) -> Dict[str, Any]:
    return {
        "id": task.todoist_id,
        "content": task.content,
        "project_id": task.project_id,
        "labels": task.labels,
        "priority": task.priority,
        "due": task.due
    }