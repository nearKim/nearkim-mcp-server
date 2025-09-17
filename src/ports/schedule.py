from abc import ABC, abstractmethod
from typing import Any, Dict


class ScheduleSummaryPort(ABC):
    @abstractmethod
    async def next_window_summary(self, days: int = 7) -> Dict[str, Any]: ...