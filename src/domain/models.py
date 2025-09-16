from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

Quadrant = Literal["Q1", "Q2", "Q3", "Q4"]


@dataclass
class ClassificationDecision:
    quadrant: Quadrant
    urgent: bool
    important: bool
    reason: str


@dataclass
class DecisionRecord(ClassificationDecision):
    todoist_id: str
    applied_mode: Literal["labels", "priorities"]
    updated_at: datetime

    @classmethod
    def from_decision(
        cls,
        todoist_id: str,
        decision: ClassificationDecision,
        applied_mode: Literal["labels", "priorities"],
        updated_at: datetime | None = None,
    ) -> "DecisionRecord":
        return cls(
            todoist_id=todoist_id,
            quadrant=decision.quadrant,
            urgent=decision.urgent,
            important=decision.important,
            reason=decision.reason,
            applied_mode=applied_mode,
            updated_at=updated_at or datetime.now(timezone.utc),
        )
