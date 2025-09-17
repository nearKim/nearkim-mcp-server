import typing
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic.dataclasses import dataclass

Quadrant = typing.Literal["Q1", "Q2", "Q3", "Q4"]


@dataclass
class FreeSlot:
    start: datetime
    end: datetime
    duration_minutes: int


@dataclass  
class FocusBlock:
    event_id: str
    task_id: str
    start: datetime
    end: datetime
    calendar_id: str


class DecisionStatus(Enum):
    SUCCESS = "success"
    FALLBACK = "fallback"
    ERROR = "error"


@dataclass
class ClassificationDecision:
    quadrant: Quadrant
    urgent: bool
    important: bool
    reason: str
    status: DecisionStatus = DecisionStatus.SUCCESS
    error_detail: Optional[str] = None
    
    @property
    def is_fallback(self) -> bool:
        return self.status == DecisionStatus.FALLBACK
    
    @classmethod
    def create_fallback(
        cls, 
        error: Exception,
        default_quadrant: Quadrant = "Q4"
    ) -> "ClassificationDecision":
        error_type = type(error).__name__
        error_msg = str(error)
        
        return cls(
            quadrant=default_quadrant,
            urgent=False,
            important=False,
            reason=f"Unable to classify task. Applied default priority.",
            status=DecisionStatus.FALLBACK,
            error_detail=f"{error_type}: {error_msg}"
        )


@dataclass
class DecisionRecord:
    quadrant: Quadrant
    urgent: bool
    important: bool
    reason: str
    todoist_id: str
    applied_mode: typing.Literal["labels", "priorities"]
    updated_at: datetime
    status: DecisionStatus = DecisionStatus.SUCCESS
    error_detail: Optional[str] = None

    @classmethod
    def from_decision(
        cls,
        todoist_id: str,
        decision: ClassificationDecision,
        applied_mode: typing.Literal["labels", "priorities"],
        updated_at: datetime | None = None,
    ) -> "DecisionRecord":
        return cls(
            quadrant=decision.quadrant,
            urgent=decision.urgent,
            important=decision.important,
            reason=decision.reason,
            status=decision.status,
            error_detail=decision.error_detail,
  
            todoist_id=todoist_id,
            applied_mode=applied_mode,
            updated_at=updated_at or datetime.now(timezone.utc),
        )
