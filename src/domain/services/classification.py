from __future__ import annotations

from typing import Optional

from ..entities import Task
from ..models import ClassificationDecision


class ClassifierService:
    """
    Domain service responsible for classifying tasks into Eisenhower quadrants.
    
    This service orchestrates the classification process by:
    1. Gathering context (user profile, calendar)
    2. Delegating to LLM for classification
    3. Returning structured classification decision
    """
    
    def __init__(self, llm, profile_repo=None, calendar_repo=None):
        self.llm = llm
        self.profile_repo = profile_repo
        self.calendar_repo = calendar_repo

    def classify(
        self, task: Task, *, force_json: bool = False
    ) -> ClassificationDecision:
        profile = self.profile_repo.load_compact_profile() if self.profile_repo else {}
        near_term = (
            self.calendar_repo.next_window_summary(days=7) if self.calendar_repo else {}
        )
        return self.llm.classify_task(task, profile, near_term, force_json=force_json)