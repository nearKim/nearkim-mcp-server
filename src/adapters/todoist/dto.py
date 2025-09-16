from __future__ import annotations

from datetime import datetime
from enum import IntEnum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Priority(IntEnum):
    P1 = 4
    P2 = 3
    P3 = 2
    P4 = 1

    @classmethod
    def from_quadrant(cls, quadrant: int) -> Priority:
        mapping = {1: cls.P1, 2: cls.P2, 3: cls.P3, 4: cls.P4}
        return mapping.get(quadrant, cls.P4)


class DueDTO(BaseModel):
    date: str
    string: Optional[str] = None
    datetime: Optional[datetime] = None
    timezone: Optional[str] = None
    is_recurring: bool = False


class LabelDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    color: str
    order: int
    is_favorite: bool


class ProjectDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    parent_id: Optional[str] = None
    order: int
    color: str
    is_favorite: bool


class TaskDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    content: str
    description: Optional[str] = None
    project_id: Optional[str] = None
    labels: list[str] = Field(default_factory=list)
    priority: int = 1
    due: Optional[dict] = None


class TaskUpdateDTO(BaseModel):
    content: Optional[str] = None
    description: Optional[str] = None
    labels: Optional[list[str]] = None
    priority: Optional[int] = None
    due_string: Optional[str] = None
    due_date: Optional[str] = None

    def to_api_params(self) -> dict:
        return {k: v for k, v in self.model_dump().items() if v is not None}


class LabelCacheDTO(BaseModel):
    by_id: dict[str, LabelDTO] = Field(default_factory=dict)
    by_name: dict[str, LabelDTO] = Field(default_factory=dict)

    def add(self, label: LabelDTO) -> None:
        self.by_id[label.id] = label
        self.by_name[label.name] = label

    def get_id(self, name: str) -> Optional[str]:
        label = self.by_name.get(name)
        return label.id if label else None

    def exists(self, name: str) -> bool:
        return name in self.by_name


class ProjectCacheDTO(BaseModel):
    by_id: dict[str, ProjectDTO] = Field(default_factory=dict)
    by_name: dict[str, ProjectDTO] = Field(default_factory=dict)

    def add(self, project: ProjectDTO) -> None:
        self.by_id[project.id] = project
        self.by_name[project.name] = project

    def get_name(self, id: str) -> Optional[str]:
        project = self.by_id.get(id)
        return project.name if project else None
