
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.adapters.todoist.adapter import TodoistAdapter
from src.domain.entities import Task
from src.domain.models import ClassificationDecision
from src.domain.repositories import DecisionRepository
from src.domain.services.classification import ClassifierService
from src.domain.services.task_ignore import TaskIgnoreService

logger = logging.getLogger(__name__)


class TodoistService:
    
    def __init__(
        self,
        adapter: TodoistAdapter,
        classifier: ClassifierService,
        ignore_service: TaskIgnoreService,
        decision_repository: DecisionRepository,
        calendar_service=None
    ):
        self.adapter = adapter
        self.classifier = classifier
        self.ignore_service = ignore_service
        self.decision_repository = decision_repository
        self.calendar_service = calendar_service
    
    async def classify_all_tasks(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        tasks = await self.adapter.fetch_tasks(project_id=project_id)
        
        results = {
            "total": len(tasks),
            "classified": 0,
            "ignored": 0,
            "failed": 0,
            "q2_scheduled": 0
        }
        
        for task_data in tasks:
            try:
                if self.ignore_service.should_ignore(task_data):
                    results["ignored"] += 1
                    continue
                
                task = Task(
                    todoist_id=task_data["id"],
                    content=task_data.get("content", ""),
                    project_id=task_data.get("project_id"),
                    labels=task_data.get("labels", []),
                    priority=task_data.get("priority", 1),
                    due=task_data.get("due")
                )
                
                decision = self.classifier.classify(task)
                
                await self.adapter.apply_eisenhower(task.todoist_id, decision)
                
                await self.decision_repository.save_decision(
                    task_id=task.todoist_id,
                    decision=decision
                )
                
                if decision.quadrant == "Q2" and self.calendar_service:
                    scheduled = await self._schedule_q2_task(task, decision)
                    if scheduled:
                        results["q2_scheduled"] += 1
                
                results["classified"] += 1
                
            except Exception as e:
                logger.error(f"Failed to classify task {task_data.get('id')}: {e}")
                results["failed"] += 1
        
        return results
    
    async def reclassify_task(self, task_id: str) -> ClassificationDecision:
        task_dto = await self.adapter.get_task(task_id)
        
        task = Task(
            todoist_id=task_dto.id,
            content=task_dto.content,
            project_id=task_dto.project_id,
            labels=task_dto.labels,
            priority=task_dto.priority,
            due=task_dto.due
        )
        
        decision = self.classifier.classify(task, force_json=True)
        
        await self.adapter.apply_eisenhower(task_id, decision)
        
        await self.decision_repository.save_decision(
            task_id=task_id,
            decision=decision
        )
        
        if decision.quadrant == "Q2" and self.calendar_service:
            await self._schedule_q2_task(task, decision)
        
        return decision
    
    async def get_quadrant_tasks(self, quadrant: str) -> List[Dict[str, Any]]:
        decisions = await self.decision_repository.get_by_quadrant(quadrant)
        
        tasks = []
        for decision in decisions:
            try:
                task_dto = await self.adapter.get_task(decision.todoist_id)
                tasks.append({
                    "id": task_dto.id,
                    "content": task_dto.content,
                    "project_id": task_dto.project_id,
                    "labels": task_dto.labels,
                    "priority": task_dto.priority,
                    "due": task_dto.due,
                    "quadrant": decision.quadrant,
                    "reason": decision.reason
                })
            except Exception as e:
                logger.warning(f"Could not fetch task {decision.todoist_id}: {e}")
        
        return tasks
    
    async def _schedule_q2_task(
        self, 
        task: Task, 
        decision: ClassificationDecision
    ) -> Optional[Dict[str, Any]]:
        if not self.calendar_service:
            return None
        
        try:
            result = await self.calendar_service.schedule_q2_task(
                task_id=task.todoist_id,
                task_content=task.content,
                min_block_minutes=90
            )
            
            if result:
                logger.info(
                    f"Scheduled Q2 task {task.todoist_id} "
                    f"for {result['start']} - {result['end']}"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to schedule Q2 task {task.todoist_id}: {e}")
            return None