from dataclasses import dataclass
from typing import Literal

Quadrant = Literal["Q1", "Q2", "Q3", "Q4"]


@dataclass
class ClassificationDecision:
    quadrant: Quadrant
    urgent: bool
    important: bool
    reason: str
