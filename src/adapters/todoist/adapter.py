from __future__ import annotations


from todoist_api_python.api_async import TodoistAPIAsync
from todoist_api_python.models import Label, Project, Task

from src.adapters.todoist.dto import LabelDTO, ProjectDTO, TaskDTO
from src.application.service.todoist import (
    CacheService,
    ClassificationService,
    LabelService,
    TaskIgnoreService,
    TaskService,
    TodoistAPIBase,
)
from src.domain.services.task_ignore import IgnoreRules
from src.bootstrap.settings.schemas import TodoistConfig
from src.domain.models import ClassificationDecision


class TodoistAPIAdapter(TodoistAPIBase):
    def __init__(self, api: TodoistAPIAsync):
        self.api = api

    async def get_task(self, task_id: str) -> TaskDTO:
        task = await self.api.get_task(task_id)
        return self._task_to_dto(task)

    async def update_task(self, task_id: str, **params) -> None:
        await self.api.update_task(task_id, **params)

    async def add_label(self, name: str) -> LabelDTO:
        label = await self.api.add_label(name=name)
        return self._label_to_dto(label)

    async def fetch_labels(self) -> list[LabelDTO]:
        labels = []
        async for label_batch in await self.api.get_labels():
            for label in label_batch:
                labels.append(self._label_to_dto(label))
        return labels

    async def fetch_projects(self) -> list[ProjectDTO]:
        projects = []
        async for project_batch in await self.api.get_projects():
            for project in project_batch:
                projects.append(self._project_to_dto(project))
        return projects

    @staticmethod
    def _task_to_dto(task: Task) -> TaskDTO:
        return TaskDTO(
            id=task.id,
            content=task.content,
            description=task.description,
            project_id=task.project_id,
            labels=task.labels,
            priority=task.priority,
            due=task.due.to_dict() if task.due else None,
        )

    @staticmethod
    def _label_to_dto(label: Label) -> LabelDTO:
        return LabelDTO(
            id=label.id,
            name=label.name,
            color=label.color,
            order=label.order,
            is_favorite=label.is_favorite,
        )

    @staticmethod
    def _project_to_dto(project: Project) -> ProjectDTO:
        return ProjectDTO(
            id=project.id,
            name=project.name,
            parent_id=project.parent_id,
            order=project.order,
            color=project.color,
            is_favorite=project.is_favorite,
        )


class TodoistAdapter:
    def __init__(self, cfg: TodoistConfig):
        self.cfg = cfg

        token = cfg.token.get_secret_value() if cfg.token else None
        sdk_api = TodoistAPIAsync(token)
        self.api_adapter = TodoistAPIAdapter(sdk_api)

        self.cache = CacheService()
        self.task_service = TaskService(self.api_adapter)
        self.label_service = LabelService(
            self.api_adapter, self.cache, cfg.classification.autocreate_labels
        )
        self.classification_service = ClassificationService(
            self.task_service, self.label_service
        )
        ignore_rules = IgnoreRules(
            project_ids=set(cfg.ignore.project_ids),
            project_names=set(cfg.ignore.projects_by_name),
            label_names=set(cfg.ignore.labels_by_name),
        )
        self.ignore_service = TaskIgnoreService(
            self.cache,
            self.api_adapter,
            ignore_rules,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.cache.clear()

    async def get_task(self, task_id: str) -> TaskDTO:
        return await self.task_service.get_task(task_id)

    async def add_labels_to_task(self, task_id: str, label_names: list[str]) -> None:
        label_map = await self.label_service.ensure_labels_exist(label_names)
        if label_map:
            valid_labels = [name for name in label_names if name in label_map]
            await self.task_service.merge_and_update_labels(task_id, valid_labels)

    async def set_priority(self, task_id: str, priority: int) -> None:
        await self.task_service.set_priority(task_id, priority)

    async def apply_eisenhower(
        self, task_id: str, decision: ClassificationDecision
    ) -> None:
        if self.cfg.classification.output == "labels":
            await self.classification_service.apply_eisenhower_as_labels(
                task_id,
                decision,
                self.cfg.classification.label_urgent,
                self.cfg.classification.label_important,
            )
        else:
            await self.classification_service.apply_eisenhower_as_priority(
                task_id, decision
            )

    async def should_ignore_task(self, task_json: dict) -> bool:
        return await self.ignore_service.should_ignore(task_json)
