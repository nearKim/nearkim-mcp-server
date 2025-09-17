from __future__ import annotations

from dataclasses import dataclass

from src.domain.entities import Task


@dataclass
class ClassifyTaskCommand:
    task: Task
    force_json: bool = False
    
    def __post_init__(self):
        if not self.task:
            raise ValueError("Task is required for classification command")