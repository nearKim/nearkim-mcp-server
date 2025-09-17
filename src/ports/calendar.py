from abc import ABC, abstractmethod


class CalendarPort(ABC):
    @abstractmethod
    async def find_free(self, days: int, min_minutes: int): ...
