from __future__ import annotations

from enum import Enum
from typing import List, Literal

from pydantic import BaseModel, Field


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    role: Role
    content: str


class ClassificationRequest(BaseModel):
    model: str
    input: List[Message] = Field(alias="messages")

    class Config:
        populate_by_name = True


class ClassificationResponse(BaseModel):
    quadrant: Literal["Q1", "Q2", "Q3", "Q4"]
    urgent: bool
    important: bool
    reason: str = ""


class EisenhowerCommandBuilder:
    """Builder for constructing Eisenhower Matrix classification commands."""

    EISENHOWER_SYSTEM = """You classify Todoist tasks via the Eisenhower Matrix as Todoist recommends:
- Q1 = Urgent + Important → do now.
- Q2 = Important, not Urgent → schedule on calendar (timebox).
- Q3 = Urgent, not Important → delegate/ninja-time.
- Q4 = not Urgent, not Important → delete/limit.
Avoid the mere-urgency effect. Prefer Q2 when long-term value exists without near-term consequence.
Output strict JSON: {quadrant, urgent, important, reason}.
"""

    def __init__(self, model: str):
        self.model = model
        self._messages: List[Message] = []
        self._add_system_prompt()

    def _add_system_prompt(self) -> EisenhowerCommandBuilder:
        self._messages.append(Message(role=Role.SYSTEM, content=self.EISENHOWER_SYSTEM))
        return self

    def with_task_context(
        self, task, profile: dict, near_term: dict
    ) -> EisenhowerCommandBuilder:
        """Add task classification context to the command."""
        user_content = (
            "Classify this Todoist task into Q1..Q4.\n"
            f"Task: {task.content}\nDue: {getattr(task, 'due', None)}\n"
            f"User profile: {profile}\nUpcoming schedule (7d): {near_term}\n"
            'Return JSON: {"quadrant":"Q1|Q2|Q3|Q4","urgent":true|false,'
            '"important":true|false,"reason":"<short>"}'
        )
        self._messages.append(Message(role=Role.USER, content=user_content))
        return self

    def build(self) -> ClassificationRequest:
        """Build the final classification request."""
        return ClassificationRequest(model=self.model, input=self._messages)
