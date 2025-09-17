from __future__ import annotations

import httpx
from typing import Any, Dict, List, Optional

from src.application.mappers.todoist_task import task_from_dict
from src.domain.entities import Task
from src.domain.models import ClassificationDecision
from src.domain.services.task_ignore import TaskIgnoreService
from src.ports.todoist import TodoistPort


class TodoistAdapter(TodoistPort):
    
    def __init__(self, api_key: str, ignore_service: Optional[TaskIgnoreService] = None):
        self.api_key = api_key
        self.base_url = "https://api.todoist.com/rest/v2"
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self.ignore_service = ignore_service
    
    async def get_task(self, task_id: str) -> Task:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/tasks/{task_id}",
                headers=self.headers
            )
            response.raise_for_status()
            task_data = response.json()
            return task_from_dict(task_data)
    
    async def update_task(self, task_id: str, **params) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/tasks/{task_id}",
                headers=self.headers,
                json=params
            )
            response.raise_for_status()
    
    async def fetch_tasks(self, project_id: Optional[str] = None) -> List[Task]:
        params = {}
        if project_id:
            params["project_id"] = project_id
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/tasks",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            tasks_data = response.json()
            return [task_from_dict(task_data) for task_data in tasks_data]
    
    async def fetch_labels(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/labels",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def fetch_projects(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/projects",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def apply_eisenhower(self, task_id: str, decision: ClassificationDecision) -> None:
        labels = []
        if decision.urgent:
            labels.append("urgent")
        if decision.important:
            labels.append("important")
        labels.append(decision.quadrant)
        
        await self.update_task(task_id, labels=labels)
    
    async def should_ignore_task(self, task: Task) -> bool:
        if not self.ignore_service:
            return False
        task_dict = {
            "id": task.todoist_id,
            "content": task.content,
            "project_id": task.project_id,
            "labels": task.labels,
            "priority": task.priority,
            "due": task.due
        }
        return self.ignore_service.should_ignore(task_dict)