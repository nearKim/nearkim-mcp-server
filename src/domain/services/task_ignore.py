from __future__ import annotations

from functools import singledispatchmethod

from ..ports.cache import EntityCache
from ..value_objects import EntityId, EntityName, LabelMatch, ProjectMatch


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
    
    def __init__(
        self, 
        project_cache: EntityCache, 
        label_cache: EntityCache, 
        ignore_rules: IgnoreRules
    ):
        self.project_cache = project_cache
        self.label_cache = label_cache
        self.ignore_rules = ignore_rules

    def should_ignore(self, task_json: dict) -> bool:
        project_id = task_json.get("project_id")
        if project_id and self._matches(ProjectMatch(project_id)):
            return True
        
        task_labels = task_json.get("labels", [])
        if task_labels and self._matches(LabelMatch(task_labels)):
            return True
        
        return False

    @singledispatchmethod
    def _matches(self, match: object) -> bool:
        raise NotImplementedError(f"Cannot match {type(match)}")
    
    @_matches.register
    def _(self, match: ProjectMatch) -> bool:
        if match.project_id in self.ignore_rules.project_ids:
            return True
        
        if not self.ignore_rules.project_names:
            return False
        
        project_name = self.project_cache.get(EntityId(match.project_id))
        return project_name in self.ignore_rules.project_names if project_name else False
    
    @_matches.register
    def _(self, match: LabelMatch) -> bool:
        if not self.ignore_rules.label_names:
            return False
        
        ignore_label_ids = {
            label_id
            for label in self.ignore_rules.label_names
            if (label_id := self.label_cache.get(EntityName(label))) is not None
        }
        
        return bool(set(match.label_ids) & ignore_label_ids)