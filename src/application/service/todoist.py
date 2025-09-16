from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Iterable, Optional, Protocol, runtime_checkable

from src.adapters.todoist.dto import (
    LabelCacheDTO,
    LabelDTO,
    Priority,
    ProjectCacheDTO,
    ProjectDTO,
    TaskDTO,
    TaskUpdateDTO,
)
from src.domain.models import ClassificationDecision


@runtime_checkable
class TodoistAPIProtocol(Protocol):
    async def get_task(self, task_id: str) -> TaskDTO:
        ...

    async def update_task(self, task_id: str, **params) -> None:
        ...

    async def add_label(self, name: str) -> LabelDTO:
        ...

    async def fetch_labels(self) -> list[LabelDTO]:
        ...

    async def fetch_projects(self) -> list[ProjectDTO]:
        ...


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


class TaskService:
    def __init__(self, api: TodoistAPIProtocol):
        self.api = api

    async def get_task(self, task_id: str) -> TaskDTO:
        return await self.api.get_task(task_id)

    async def update_task(self, task_id: str, update: TaskUpdateDTO) -> None:
        params = update.to_api_params()
        if params:
            await self.api.update_task(task_id, **params)

    async def set_priority(self, task_id: str, priority: int) -> None:
        update = TaskUpdateDTO(priority=priority)
        await self.update_task(task_id, update)

    async def merge_and_update_labels(
        self, task_id: str, label_names: list[str]
    ) -> None:
        if not label_names:
            return
        task = await self.get_task(task_id)
        current_labels = set(task.labels)
        new_labels = {name.lstrip("@") for name in label_names}
        merged_labels = list(current_labels | new_labels)
        if merged_labels != task.labels:
            update = TaskUpdateDTO(labels=merged_labels)
            await self.update_task(task_id, update)


class LabelService:
    def __init__(
        self, api: TodoistAPIProtocol, cache: CacheService, autocreate: bool = False
    ):
        self.api = api
        self.cache = cache
        self.autocreate = autocreate

    async def ensure_cache_loaded(self) -> None:
        if not self.cache.is_labels_cached():
            labels = await self.api.fetch_labels()
            self.cache.populate_labels(labels)

    async def ensure_labels_exist(self, names: Iterable[str]) -> dict[str, str]:
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


class ClassificationService:
    def __init__(self, task_service: TaskService, label_service: LabelService):
        self.task_service = task_service
        self.label_service = label_service

    async def apply_eisenhower_as_labels(
        self,
        task_id: str,
        decision: ClassificationDecision,
        urgent_label: str,
        important_label: str,
    ) -> None:
        labels = []
        if decision.urgent:
            labels.append(urgent_label)
        if decision.important:
            labels.append(important_label)
        if labels:
            label_map = await self.label_service.ensure_labels_exist(labels)
            valid_labels = [name for name in labels if name in label_map]
            await self.task_service.merge_and_update_labels(task_id, valid_labels)

    async def apply_eisenhower_as_priority(
        self, task_id: str, decision: ClassificationDecision
    ) -> None:
        priority = Priority.from_quadrant(decision.quadrant)
        await self.task_service.set_priority(task_id, priority.value)


class TaskIgnoreService:
    def __init__(
        self,
        cache: CacheService,
        api: TodoistAPIProtocol,
        ignore_project_ids: set[str],
        ignore_projects_by_name: set[str],
        ignore_labels_by_name: set[str],
    ):
        self.cache = cache
        self.api = api
        self.ignore_project_ids = ignore_project_ids
        self.ignore_projects_by_name = ignore_projects_by_name
        self.ignore_labels_by_name = ignore_labels_by_name

    async def ensure_caches_loaded(self) -> None:
        tasks = []
        if not self.cache.is_labels_cached():
            tasks.append(self._load_labels())
        if not self.cache.is_projects_cached():
            tasks.append(self._load_projects())
        if tasks:
            await asyncio.gather(*tasks)

    async def _load_labels(self) -> None:
        labels = await self.api.fetch_labels()
        self.cache.populate_labels(labels)

    async def _load_projects(self) -> None:
        projects = await self.api.fetch_projects()
        self.cache.populate_projects(projects)

    async def should_ignore(self, task_json: dict) -> bool:
        await self.ensure_caches_loaded()
        project_id = task_json.get("project_id")
        if project_id:
            if project_id in self.ignore_project_ids:
                return True
            if self.ignore_projects_by_name:
                project_name = self.cache.projects.get_name(project_id)
                if project_name and project_name in self.ignore_projects_by_name:
                    return True
        if not self.ignore_labels_by_name:
            return False
        task_labels = set(task_json.get("labels", []))
        if not task_labels:
            return False
        ignore_label_ids = {
            self.cache.labels.get_id(label)
            for label in self.ignore_labels_by_name
            if self.cache.labels.get_id(label) is not None
        }
        return bool(task_labels & ignore_label_ids)
