"""Calendar scheduling port for Q2 task automation."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class CalendarSchedulingPort(ABC):
    """Port for scheduling Q2 tasks in calendar."""
    
    @abstractmethod
    async def schedule_q2_task(
        self, 
        task_id: str, 
        task_content: str,
        min_block_minutes: int = 90
    ) -> Optional[Dict[str, Any]]:
        """
        Schedule a Q2 task in the calendar.
        
        Args:
            task_id: The Todoist task ID
            task_content: Task description for the calendar event
            min_block_minutes: Minimum time block in minutes
            
        Returns:
            Dictionary with scheduling details (event_id, start, end) or None
        """
        ...
    
    @abstractmethod
    async def cancel_scheduled_task(self, event_id: str) -> bool:
        """
        Cancel a previously scheduled task.
        
        Args:
            event_id: The calendar event ID to cancel
            
        Returns:
            True if canceled successfully, False otherwise
        """
        ...