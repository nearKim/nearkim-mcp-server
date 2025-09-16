from abc import ABC, abstractmethod
from typing import Any


class LLMPort(ABC):
    @abstractmethod
    def classify_task(self, task, profile, near_term) -> Any:
        ...
