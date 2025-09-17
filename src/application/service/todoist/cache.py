"""Cache service for Todoist entities."""

from __future__ import annotations

from src.adapters.todoist.dto import (
    LabelCacheDTO,
    LabelDTO,
    ProjectCacheDTO,
    ProjectDTO,
)


class CacheService:
    """
    Manages in-memory caches for Todoist labels and projects.
    
    This service provides efficient lookups for frequently accessed
    entities, reducing API calls to Todoist.
    """
    
    def __init__(self):
        self._label_cache = LabelCacheDTO()
        self._project_cache = ProjectCacheDTO()
        self._labels_loaded = False
        self._projects_loaded = False

    @property
    def labels(self) -> LabelCacheDTO:
        """Get the label cache."""
        return self._label_cache

    @property
    def projects(self) -> ProjectCacheDTO:
        """Get the project cache."""
        return self._project_cache

    def is_labels_cached(self) -> bool:
        """Check if labels have been loaded into cache."""
        return self._labels_loaded

    def is_projects_cached(self) -> bool:
        """Check if projects have been loaded into cache."""
        return self._projects_loaded

    def populate_labels(self, labels: list[LabelDTO]) -> None:
        """Populate the label cache with a list of labels."""
        for label in labels:
            self._label_cache.add(label)
        self._labels_loaded = True

    def populate_projects(self, projects: list[ProjectDTO]) -> None:
        """Populate the project cache with a list of projects."""
        for project in projects:
            self._project_cache.add(project)
        self._projects_loaded = True

    def clear(self) -> None:
        """Clear all caches and reset loaded flags."""
        self._label_cache = LabelCacheDTO()
        self._project_cache = ProjectCacheDTO()
        self._labels_loaded = False
        self._projects_loaded = False