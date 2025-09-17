from __future__ import annotations

from abc import ABC, abstractmethod
from functools import singledispatchmethod
from typing import Optional

from ..value_objects import EntityId, EntityName


class EntityCache(ABC):
    """
    Port interface for bidirectional entity lookups.
    
    This is a domain port that defines the caching capability
    required by the domain layer. Infrastructure layer must
    provide implementations of this interface.
    
    Uses singledispatch for polymorphic get operations based on
    query type (EntityId vs EntityName).
    """
    
    @singledispatchmethod
    @abstractmethod
    def get(self, query: object) -> Optional[str]:
        raise NotImplementedError(f"Cannot query with {type(query)}")
    
    @get.register
    @abstractmethod
    def _(self, query: EntityId) -> Optional[str]:
        """Get entity name by ID."""
        pass
    
    @get.register
    @abstractmethod
    def _(self, query: EntityName) -> Optional[str]:
        """Get entity ID by name."""
        pass