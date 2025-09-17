from __future__ import annotations

import pytest
from datetime import datetime
from typing import Any, Dict

from src.application.mappers.todoist_task import task_from_dict, task_from_dto
from src.domain.entities import Task


class TestTodoistTaskMapper:

    def test_task_from_dict_minimal(self):
        task_data = {
            "id": "123",
            "content": "Test task"
        }
        
        task = task_from_dict(task_data)
        
        assert task.todoist_id == "123"
        assert task.content == "Test task"
        assert task.project_id is None
        assert task.labels == []
        assert task.priority == 1
        assert task.due is None

    def test_task_from_dict_complete(self):
        task_data = {
            "id": "456",
            "content": "Complete task",
            "project_id": "proj_789",
            "labels": ["urgent", "important"],
            "priority": 4,
            "due": {
                "date": "2024-03-15",
                "datetime": "2024-03-15T10:00:00Z"
            }
        }
        
        task = task_from_dict(task_data)
        
        assert task.todoist_id == "456"
        assert task.content == "Complete task"
        assert task.project_id == "proj_789"
        assert task.labels == ["urgent", "important"]
        assert task.priority == 4
        assert task.due == {
            "date": "2024-03-15",
            "datetime": "2024-03-15T10:00:00Z"
        }

    def test_task_from_dict_missing_id_uses_empty_string(self):
        task_data = {
            "content": "No ID task"
        }
        
        task = task_from_dict(task_data)
        
        assert task.todoist_id == ""
        assert task.content == "No ID task"

    def test_task_from_dict_null_labels(self):
        task_data = {
            "id": "789",
            "content": "Task with null labels",
            "labels": None
        }
        
        task = task_from_dict(task_data)
        
        assert task.todoist_id == "789"
        assert task.labels == []

    def test_task_from_dict_missing_priority_defaults_to_1(self):
        task_data = {
            "id": "111",
            "content": "No priority task"
        }
        
        task = task_from_dict(task_data)
        
        assert task.priority == 1

    def test_task_from_dto_is_alias_for_task_from_dict(self):
        task_data = {
            "id": "999",
            "content": "DTO test"
        }
        
        task1 = task_from_dict(task_data)
        task2 = task_from_dto(task_data)
        
        assert task1.todoist_id == task2.todoist_id
        assert task1.content == task2.content
        assert task1.project_id == task2.project_id
        assert task1.labels == task2.labels
        assert task1.priority == task2.priority
        assert task1.due == task2.due

    def test_task_from_dict_handles_empty_dict(self):
        task_data = {}
        
        task = task_from_dict(task_data)
        
        assert task.todoist_id == ""
        assert task.content == ""
        assert task.project_id is None
        assert task.labels == []
        assert task.priority == 1
        assert task.due is None

    def test_task_from_dict_preserves_due_structure(self):
        due_variants = [
            {"date": "2024-03-20"},
            {"datetime": "2024-03-20T15:30:00"},
            {"date": "2024-03-20", "datetime": "2024-03-20T15:30:00", "timezone": "UTC"},
            "2024-03-20"
        ]
        
        for due in due_variants:
            task_data = {
                "id": "test",
                "content": "Test",
                "due": due
            }
            
            task = task_from_dict(task_data)
            assert task.due == due

    def test_task_from_dict_handles_integer_id(self):
        task_data = {
            "id": 12345,
            "content": "Integer ID task"
        }
        
        task = task_from_dict(task_data)
        
        assert task.todoist_id == "12345"
        assert isinstance(task.todoist_id, str)

    def test_task_from_dict_preserves_extra_fields_in_due(self):
        task_data = {
            "id": "extra",
            "content": "Extra fields test",
            "due": {
                "date": "2024-03-15",
                "datetime": "2024-03-15T10:00:00Z",
                "timezone": "America/New_York",
                "is_recurring": True,
                "string": "every weekday"
            }
        }
        
        task = task_from_dict(task_data)
        
        assert task.due["date"] == "2024-03-15"
        assert task.due["datetime"] == "2024-03-15T10:00:00Z"
        assert task.due["timezone"] == "America/New_York"
        assert task.due["is_recurring"] is True
        assert task.due["string"] == "every weekday"