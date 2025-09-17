from __future__ import annotations

from typing import Dict, Any


class IgnoreRules:
    
    def __init__(
        self,
        project_ids: set[str] = None,
        project_names: set[str] = None,
        label_names: set[str] = None
    ):
        self.project_ids = project_ids or set()
        self.project_names = project_names or set()
        self.label_names = label_names or set()


class TaskIgnoreService:
    """Service to determine if tasks should be ignored based on rules."""
    
    def __init__(self, ignore_rules: IgnoreRules):
        self.ignore_rules = ignore_rules

    def should_ignore(self, task_json: Dict[str, Any]) -> bool:
        """Check if a task should be ignored based on project ID or labels."""
        # Check project ID
        project_id = task_json.get("project_id")
        if project_id and project_id in self.ignore_rules.project_ids:
            return True
        
        # Check labels
        task_labels = task_json.get("labels", [])
        if task_labels:
            label_set = set(task_labels) if isinstance(task_labels, list) else {task_labels}
            if label_set & self.ignore_rules.label_names:
                return True
        
        # Note: project_names checking would require a cache/lookup which we've removed
        # for simplicity. Can be added back if needed.
        
        return False