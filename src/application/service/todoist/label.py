"""Label service for Todoist operations."""

from __future__ import annotations

from typing import Iterable

from .api import TodoistAPIBase
from .cache import CacheService


class LabelService:
    """
    Service for managing Todoist labels.
    
    Handles label caching, creation, and ensuring labels exist
    before they're applied to tasks.
    """
    
    def __init__(
        self, api: TodoistAPIBase, cache: CacheService, autocreate: bool = False
    ):
        self.api = api
        self.cache = cache
        self.autocreate = autocreate

    async def ensure_cache_loaded(self) -> None:
        """Ensure the label cache is populated from the API."""
        if not self.cache.is_labels_cached():
            labels = await self.api.fetch_labels()
            self.cache.populate_labels(labels)

    async def ensure_labels_exist(self, names: Iterable[str]) -> dict[str, str]:
        """
        Ensure labels exist, creating them if autocreate is enabled.
        
        Args:
            names: Label names to ensure exist (@ prefix optional)
            
        Returns:
            Dictionary mapping label names to their IDs
        """
        await self.ensure_cache_loaded()
        label_map: dict[str, str] = {}
        for name in names:
            plain = name.lstrip("@")
            label_id = self.cache.labels.get_id(plain)
            if label_id:
                label_map[name] = label_id
                continue
            if not self.autocreate:
                continue
            new_label = await self.api.add_label(plain)
            self.cache.labels.add(new_label)
            label_map[name] = new_label.id
        return label_map