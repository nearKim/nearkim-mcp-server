"""Service for determining if tasks should be ignored."""

from __future__ import annotations

import asyncio

from src.domain.services.task_ignore import (
    IgnoreRules,
    TaskIgnoreService as DomainTaskIgnoreService,
)
from .api import TodoistAPIBase
from .cache import CacheService


class TaskIgnoreService:
    """
    Application service for determining if tasks should be ignored.
    
    Coordinates cache loading and delegates to the domain service
    for the actual ignore logic based on projects and labels.
    """
    
    def __init__(
        self,
        cache: CacheService,
        api: TodoistAPIBase,
        ignore_rules: IgnoreRules,
    ):
        self.cache = cache
        self.api = api
        self.domain_service = DomainTaskIgnoreService(
            project_cache=cache.projects,
            label_cache=cache.labels,
            ignore_rules=ignore_rules
        )

    async def ensure_caches_loaded(self) -> None:
        """Ensure both label and project caches are populated."""
        tasks = []
        if not self.cache.is_labels_cached():
            tasks.append(self._load_labels())
        if not self.cache.is_projects_cached():
            tasks.append(self._load_projects())
        if tasks:
            await asyncio.gather(*tasks)

    async def _load_labels(self) -> None:
        """Load labels from API into cache."""
        labels = await self.api.fetch_labels()
        self.cache.populate_labels(labels)

    async def _load_projects(self) -> None:
        """Load projects from API into cache."""
        projects = await self.api.fetch_projects()
        self.cache.populate_projects(projects)

    async def should_ignore(self, task_json: dict) -> bool:
        """
        Determine if a task should be ignored based on rules.
        
        Args:
            task_json: Raw task data from Todoist webhook
            
        Returns:
            True if the task should be ignored, False otherwise
        """
        await self.ensure_caches_loaded()
        return self.domain_service.should_ignore(task_json)