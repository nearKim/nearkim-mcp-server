
from __future__ import annotations

from src.adapters.todoist.dto import (
    LabelCacheDTO,
    LabelDTO,
    ProjectCacheDTO,
    ProjectDTO,
)


class CacheService:
    
    def __init__(self):
        self._label_cache = LabelCacheDTO()
        self._project_cache = ProjectCacheDTO()
        self._labels_loaded = False
        self._projects_loaded = False

    @property
    def labels(self) -> LabelCacheDTO:
        return self._label_cache

    @property
    def projects(self) -> ProjectCacheDTO:
        return self._project_cache

    def is_labels_cached(self) -> bool:
        return self._labels_loaded

    def is_projects_cached(self) -> bool:
        return self._projects_loaded

    def populate_labels(self, labels: list[LabelDTO]) -> None:
        for label in labels:
            self._label_cache.add(label)
        self._labels_loaded = True

    def populate_projects(self, projects: list[ProjectDTO]) -> None:
        for project in projects:
            self._project_cache.add(project)
        self._projects_loaded = True

    def clear(self) -> None:
        self._label_cache = LabelCacheDTO()
        self._project_cache = ProjectCacheDTO()
        self._labels_loaded = False
        self._projects_loaded = False