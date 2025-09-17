from __future__ import annotations


from ..entities import Task
from ..models import ClassificationDecision


class ClassifierService:
    
    def __init__(self, llm, profile_port=None, schedule_port=None):
        self.llm = llm
        self.profile_port = profile_port
        self.schedule_port = schedule_port

    async def classify(
        self, task: Task, *, force_json: bool = False
    ) -> ClassificationDecision:
        profile = await self.profile_port.load_compact_profile() if self.profile_port else {}
        near_term = (
            await self.schedule_port.next_window_summary(days=7) if self.schedule_port else {}
        )
        return self.llm.classify_task(task, profile, near_term, force_json=force_json)