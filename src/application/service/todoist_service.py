
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.domain.entities import Task
from src.domain.models import ClassificationDecision, DecisionRecord
from src.domain.repositories import DecisionRepository
from src.domain.services.classification import ClassifierService
from src.ports.todoist import TodoistPort

logger = logging.getLogger(__name__)


class TodoistService:
    
    def __init__(
        self,
        adapter: TodoistPort,
        classifier: ClassifierService,
        decision_repository: DecisionRepository,
        output_mode: str = "labels",
        calendar_service=None
    ):
        self.adapter = adapter
        self.classifier = classifier
        self.decision_repository = decision_repository
        self.output_mode = output_mode
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
        
        for task in tasks:
            try:
                if await self.adapter.should_ignore_task(task):
                    results["ignored"] += 1
                    continue
                
                decision = await self.classifier.classify(task)
                
                await self.adapter.apply_eisenhower(task.todoist_id, decision)
                await self.save_decision(task.todoist_id, decision)
                
                if decision.quadrant == "Q2" and self.calendar_service:
                    scheduled = await self._schedule_q2_task(task, decision)
                    if scheduled:
                        results["q2_scheduled"] += 1
                
                results["classified"] += 1
                
            except Exception as e:
                logger.error(f"Failed to classify task {task.todoist_id}: {e}")
                results["failed"] += 1
        
        return results
    
    async def save_decision(self, task_id: str, decision: ClassificationDecision) -> None:
        record = DecisionRecord.from_decision(
            todoist_id=task_id,
            decision=decision,
            applied_mode=self.output_mode
        )
        await self.decision_repository.save(record)
    
    async def reclassify_task(self, task_id: str) -> ClassificationDecision:
        task = await self.adapter.get_task(task_id)
        
        decision = await self.classifier.classify(task, force_json=True)
        
        await self.adapter.apply_eisenhower(task_id, decision)
        await self.save_decision(task_id, decision)
        
        if decision.quadrant == "Q2" and self.calendar_service:
            await self._schedule_q2_task(task, decision)
        
        return decision
    
    async def get_quadrant_tasks(self, quadrant: str) -> List[Dict[str, Any]]:
        decisions = await self.decision_repository.get_by_quadrant(quadrant)
        
        tasks = []
        for decision in decisions:
            try:
                task = await self.adapter.get_task(decision.todoist_id)
                tasks.append({
                    "id": task.todoist_id,
                    "content": task.content,
                    "project_id": task.project_id,
                    "labels": task.labels,
                    "priority": task.priority,
                    "due": task.due,
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