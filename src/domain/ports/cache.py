from __future__ import annotations

from abc import ABC, abstractmethod
from functools import singledispatchmethod
from typing import Optional

from ..value_objects import EntityId, EntityName


class EntityCache(ABC):
    
    @singledispatchmethod
    @abstractmethod
    def get(self, query: object) -> Optional[str]:
        raise NotImplementedError(f"Cannot query with {type(query)}")
    
    @get.register
    @abstractmethod
    def _(self, query: EntityId) -> Optional[str]:
        pass
    
    @get.register
    @abstractmethod
    def _(self, query: EntityName) -> Optional[str]:
        pass