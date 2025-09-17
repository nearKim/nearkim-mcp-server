from __future__ import annotations

from dataclasses import dataclass

from src.domain.entities import Task


@dataclass
class ClassifyTaskCommand:
    """
    Command to classify a task into Eisenhower quadrants.
    
    This is a command object that encapsulates all data needed
    to perform task classification. Following the Command pattern,
    it represents an intent to perform a business operation.
    
    Attributes:
        task: The task entity to classify
        force_json: Whether to force JSON output from LLM
    """
    task: Task
    force_json: bool = False
    
    def __post_init__(self):
        if not self.task:
            raise ValueError("Task is required for classification command")