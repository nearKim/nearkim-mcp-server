from __future__ import annotations

import hmac
import hashlib
import httpx
from typing import Any, Dict, List, Optional

from src.application.mappers.todoist_task import task_from_dict
from src.domain.entities import Task
from src.domain.models import ClassificationDecision
from src.domain.services.task_ignore import TaskIgnoreService
from src.ports.todoist import TodoistPort


class TodoistAdapter(TodoistPort):
    
    def __init__(self, api_key: str, ignore_service: Optional[TaskIgnoreService] = None,
                 webhook_secret: Optional[str] = None):
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.base_url = "https://api.todoist.com/rest/v2"
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self.ignore_service = ignore_service
        self._label_cache = {}
        self._manual_overrides = set()
    async def get_task(self, task_id: str) -> Task:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/tasks/{task_id}",
                headers=self.headers
            )
            response.raise_for_status()
            task_data = response.json()
            return task_from_dict(task_data)
    
    async def fetch_tasks(self, project_id: Optional[str] = None, 
                         filter_str: Optional[str] = None) -> List[Task]:
        params = {}
        if project_id:
            params["project_id"] = project_id
        if filter_str:
            params["filter"] = filter_str
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/tasks",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            tasks_data = response.json()
            return [task_from_dict(task_data) for task_data in tasks_data]
    
    async def create_task(self, content: str, **kwargs) -> Task:
        task_data = {"content": content, **kwargs}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/tasks",
                headers=self.headers,
                json=task_data
            )
            response.raise_for_status()
            return task_from_dict(response.json())
    
    async def update_task(self, task_id: str, **updates) -> Task:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/tasks/{task_id}",
                headers=self.headers,
                json=updates
            )
            response.raise_for_status()
            return task_from_dict(response.json())
    
    async def delete_task(self, task_id: str) -> bool:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/tasks/{task_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.status_code == 204
    
    async def complete_task(self, task_id: str) -> bool:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/tasks/{task_id}/close",
                headers=self.headers
            )
            response.raise_for_status()
            return response.status_code == 204
    async def apply_eisenhower(self, task_id: str, decision: ClassificationDecision) -> None:
        await self.remove_eisenhower_labels(task_id)
        labels = []
        if decision.urgent:
            labels.append("@urgent")
        if decision.important:
            labels.append("@important")
        labels.append(decision.quadrant)
        label_ids = []
        for label_name in labels:
            label_id = await self.ensure_label_exists(label_name)
            label_ids.append(label_id)
        await self.update_task(task_id, label_ids=label_ids)
        comment = f"Classified as {decision.quadrant}: {decision.reason}"
        await self.add_comment(task_id, comment)
    
    async def remove_eisenhower_labels(self, task_id: str) -> None:
        task = await self.get_task(task_id)
        eisenhower_labels = ["@urgent", "@important", "Q1", "Q2", "Q3", "Q4"]
        remaining_labels = [label for label in task.labels 
                          if label not in eisenhower_labels]
        
        await self.update_task(task_id, labels=remaining_labels)
    async def add_labels(self, task_id: str, labels: List[str]) -> None:
        task = await self.get_task(task_id)
        current_labels = set(task.labels)
        current_labels.update(labels)
        label_ids = []
        for label_name in current_labels:
            label_id = await self.ensure_label_exists(label_name)
            label_ids.append(label_id)
        
        await self.update_task(task_id, label_ids=label_ids)
    
    async def remove_labels(self, task_id: str, labels: List[str]) -> None:
        task = await self.get_task(task_id)
        current_labels = set(task.labels)
        for label in labels:
            current_labels.discard(label)
        label_ids = []
        for label_name in current_labels:
            label_id = await self.ensure_label_exists(label_name)
            label_ids.append(label_id)
        
        await self.update_task(task_id, label_ids=label_ids)
    
    async def ensure_label_exists(self, label_name: str) -> str:
        if label_name in self._label_cache:
            return self._label_cache[label_name]
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/labels",
                headers=self.headers
            )
            response.raise_for_status()
            labels = response.json()
        for label in labels:
            self._label_cache[label["name"]] = label["id"]
            if label["name"] == label_name:
                return label["id"]
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/labels",
                headers=self.headers,
                json={"name": label_name}
            )
            response.raise_for_status()
            new_label = response.json()
            self._label_cache[label_name] = new_label["id"]
            return new_label["id"]
    async def set_priority(self, task_id: str, priority: int) -> None:
        todoist_priority = 5 - priority
        await self.update_task(task_id, priority=todoist_priority)
    async def should_ignore_task(self, task: Task) -> bool:
        if task.todoist_id in self._manual_overrides:
            return False
        
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
    
    async def set_manual_override(self, task_id: str, override: bool) -> None:
        if override:
            self._manual_overrides.add(task_id)
            await self.add_comment(task_id, "Manual classification override enabled")
        else:
            self._manual_overrides.discard(task_id)
            await self.add_comment(task_id, "Manual classification override disabled")
    async def get_projects(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/projects",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def get_project(self, project_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/projects/{project_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    async def add_comment(self, task_id: str, content: str) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/comments",
                headers=self.headers,
                json={
                    "task_id": task_id,
                    "content": content
                }
            )
            response.raise_for_status()
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        if not self.webhook_secret:
            return True
        
        expected_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)
    async def fetch_labels(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/labels",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def fetch_projects(self) -> List[Dict[str, Any]]:
        return await self.get_projects()