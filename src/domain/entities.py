from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Task:
    todoist_id: str
    content: str
    due: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    project_id: Optional[str] = None
