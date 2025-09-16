from typing import Optional, Protocol

from .entities import Task
from .models import ClassificationDecision


class ClassifierService:
    def __init__(self, llm, profile_repo=None, calendar_repo=None):
        self.llm = llm
        self.profile_repo = profile_repo
        self.calendar_repo = calendar_repo

    def classify(self, task: Task) -> ClassificationDecision:
        profile = self.profile_repo.load_compact_profile() if self.profile_repo else {}
        near_term = (
            self.calendar_repo.next_window_summary(days=7) if self.calendar_repo else {}
        )
        return self.llm.classify_task(task, profile, near_term)


class ProjectCache(Protocol):
    def get_name(self, project_id: str) -> Optional[str]:
        ...


class LabelCache(Protocol):
    def get_id(self, label_name: str) -> Optional[str]:
        ...


class IgnoreConfig(Protocol):
    @property
    def project_ids(self) -> set[str]:
        ...

    @property
    def projects_by_name(self) -> set[str]:
        ...

    @property
    def labels_by_name(self) -> set[str]:
        ...


class TaskIgnoreService:
    def __init__(
        self, project_cache: ProjectCache, label_cache: LabelCache, config: IgnoreConfig
    ):
        self.project_cache = project_cache
        self.label_cache = label_cache
        self.config = config

    def should_ignore(self, task_json: dict) -> bool:
        if self._should_ignore_by_project(task_json.get("project_id")):
            return True
        return self._should_ignore_by_labels(task_json.get("labels", []))

    def _should_ignore_by_project(self, project_id: Optional[str]) -> bool:
        if not project_id:
            return False

        if project_id in self.config.project_ids:
            return True

        if not self.config.projects_by_name:
            return False

        project_name = self.project_cache.get_name(project_id)
        return project_name in self.config.projects_by_name if project_name else False

    def _should_ignore_by_labels(self, task_labels: list[str]) -> bool:
        if not self.config.labels_by_name or not task_labels:
            return False

        task_label_set = set(task_labels)
        ignore_label_ids = {
            self.label_cache.get_id(label)
            for label in self.config.labels_by_name
            if self.label_cache.get_id(label) is not None
        }

        return bool(task_label_set & ignore_label_ids)
