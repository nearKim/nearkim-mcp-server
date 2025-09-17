from abc import ABC, abstractmethod
from typing import Any, Dict


class ProfilePort(ABC):
    @abstractmethod
    async def load_compact_profile(self) -> Dict[str, Any]: ...