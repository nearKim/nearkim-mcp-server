from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntityId:
    value: str
    
    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise ValueError("EntityId cannot be empty")


@dataclass(frozen=True)
class EntityName:
    value: str
    
    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise ValueError("EntityName cannot be empty")


@dataclass(frozen=True)
class ProjectMatch:
    project_id: str


@dataclass(frozen=True)
class LabelMatch:
    label_ids: list[str]