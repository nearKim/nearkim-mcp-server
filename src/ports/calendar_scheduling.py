from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class CalendarSchedulingPort(ABC):
    
    @abstractmethod
    async def schedule_q2_task(
        self, 
        task_id: str, 
        task_content: str,
        min_block_minutes: int = 90
    ) -> Optional[Dict[str, Any]]:
        ...
    
    @abstractmethod
    async def cancel_scheduled_task(self, event_id: str) -> bool:
        ...