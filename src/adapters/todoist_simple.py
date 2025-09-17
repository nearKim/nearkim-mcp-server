from __future__ import annotations

import httpx
from typing import Any, Dict, List, Optional

from src.domain.models import ClassificationDecision


class TodoistAdapter:
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.todoist.com/rest/v2"
        self.headers = {"Authorization": f"Bearer {api_key}"}
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/tasks/{task_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def update_task(self, task_id: str, **params) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/tasks/{task_id}",
                headers=self.headers,
                json=params
            )
            response.raise_for_status()
    
    async def fetch_tasks(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
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
            return response.json()
    
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