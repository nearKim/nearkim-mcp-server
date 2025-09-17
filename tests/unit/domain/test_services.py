"""Tests for domain services."""

import pytest
from unittest.mock import MagicMock, Mock

from src.domain.services.classification import ClassifierService
from src.domain.services.task_ignore import IgnoreRules, TaskIgnoreService
from src.domain.entities import Task
from src.domain.models import ClassificationDecision, DecisionStatus
from src.domain.value_objects import EntityId, EntityName


class TestClassifierService:
    """Test ClassifierService."""
    
    def test_classify_with_all_repos(self):
        """Test classification with profile and calendar repos."""
        # Setup
        mock_llm = MagicMock()
        mock_profile_repo = MagicMock()
        mock_calendar_repo = MagicMock()
        
        mock_profile_repo.load_compact_profile.return_value = {"name": "John"}
        mock_calendar_repo.next_window_summary.return_value = {"meetings": 5}
        
        expected_decision = ClassificationDecision(
            quadrant="Q1",
            urgent=True,
            important=True,
            reason="Test"
        )
        mock_llm.classify_task.return_value = expected_decision
        
        service = ClassifierService(
            llm=mock_llm,
            profile_repo=mock_profile_repo,
            calendar_repo=mock_calendar_repo
        )
        
        task = Task(
            todoist_id="123",
            content="Test task",
            project_id="proj_1",
            labels=[]
        )
        
        # Execute
        result = service.classify(task)
        
        # Verify
        assert result == expected_decision
        mock_profile_repo.load_compact_profile.assert_called_once()
        mock_calendar_repo.next_window_summary.assert_called_once_with(days=7)
        mock_llm.classify_task.assert_called_once_with(
            task,
            {"name": "John"},
            {"meetings": 5},
            force_json=False
        )
    
    def test_classify_without_repos(self):
        """Test classification without profile and calendar repos."""
        mock_llm = MagicMock()
        expected_decision = ClassificationDecision(
            quadrant="Q2",
            urgent=False,
            important=True,
            reason="Test"
        )
        mock_llm.classify_task.return_value = expected_decision
        
        service = ClassifierService(llm=mock_llm)
        
        task = Task(
            todoist_id="456",
            content="Another task",
            project_id="proj_2",
            labels=[]
        )
        
        result = service.classify(task, force_json=True)
        
        assert result == expected_decision
        mock_llm.classify_task.assert_called_once_with(
            task,
            {},
            {},
            force_json=True
        )


class TestIgnoreRules:
    """Test IgnoreRules value object."""
    
    def test_ignore_rules_creation(self):
        """Test creating IgnoreRules."""
        rules = IgnoreRules(
            project_ids={"proj_1", "proj_2"},
            project_names={"Personal", "Archive"},
            label_names={"no-eisenhower", "recurring"}
        )
        
        assert rules.project_ids == {"proj_1", "proj_2"}
        assert rules.project_names == {"Personal", "Archive"}
        assert rules.label_names == {"no-eisenhower", "recurring"}
    
    def test_ignore_rules_defaults(self):
        """Test IgnoreRules with defaults."""
        rules = IgnoreRules()
        
        assert rules.project_ids == set()
        assert rules.project_names == set()
        assert rules.label_names == set()


class TestTaskIgnoreService:
    """Test TaskIgnoreService."""
    
    @pytest.fixture
    def mock_project_cache(self):
        """Create mock project cache."""
        cache = Mock()
        cache.get = Mock(side_effect=self._cache_get_handler)
        return cache
    
    @pytest.fixture
    def mock_label_cache(self):
        """Create mock label cache."""
        cache = Mock()
        cache.get = Mock(side_effect=self._cache_get_handler)
        return cache
    
    def _cache_get_handler(self, query):
        """Handle cache.get() calls based on query type."""
        if isinstance(query, EntityId):
            # Simulate project ID lookups
            if query.value == "proj_ignore":
                return "Ignored Project"
            elif query.value == "proj_ok":
                return "Good Project"
        elif isinstance(query, EntityName):
            # Simulate label name lookups
            if query.value == "no-eisenhower":
                return "label_ignore"
            elif query.value == "work":
                return "label_ok"
        return None
    
    def test_should_ignore_by_project_id(self, mock_project_cache, mock_label_cache):
        """Test ignoring task by project ID."""
        rules = IgnoreRules(
            project_ids={"proj_ignore"},
            project_names=set(),
            label_names=set()
        )
        
        service = TaskIgnoreService(
            project_cache=mock_project_cache,
            label_cache=mock_label_cache,
            ignore_rules=rules
        )
        
        task_json = {
            "project_id": "proj_ignore",
            "labels": []
        }
        
        assert service.should_ignore(task_json) is True
    
    def test_should_ignore_by_project_name(self, mock_project_cache, mock_label_cache):
        """Test ignoring task by project name."""
        rules = IgnoreRules(
            project_ids=set(),
            project_names={"Ignored Project"},
            label_names=set()
        )
        
        service = TaskIgnoreService(
            project_cache=mock_project_cache,
            label_cache=mock_label_cache,
            ignore_rules=rules
        )
        
        task_json = {
            "project_id": "proj_ignore",  # Maps to "Ignored Project"
            "labels": []
        }
        
        assert service.should_ignore(task_json) is True
    
    def test_should_ignore_by_label(self, mock_project_cache, mock_label_cache):
        """Test ignoring task by label."""
        rules = IgnoreRules(
            project_ids=set(),
            project_names=set(),
            label_names={"no-eisenhower"}
        )
        
        service = TaskIgnoreService(
            project_cache=mock_project_cache,
            label_cache=mock_label_cache,
            ignore_rules=rules
        )
        
        task_json = {
            "project_id": "proj_ok",
            "labels": ["label_ignore", "label_ok"]  # label_ignore maps to no-eisenhower
        }
        
        assert service.should_ignore(task_json) is True
    
    def test_should_not_ignore(self, mock_project_cache, mock_label_cache):
        """Test task that should not be ignored."""
        rules = IgnoreRules(
            project_ids={"proj_ignore"},
            project_names={"Archive"},
            label_names={"no-eisenhower"}
        )
        
        service = TaskIgnoreService(
            project_cache=mock_project_cache,
            label_cache=mock_label_cache,
            ignore_rules=rules
        )
        
        task_json = {
            "project_id": "proj_ok",
            "labels": ["label_ok"]
        }
        
        assert service.should_ignore(task_json) is False
    
    def test_should_not_ignore_empty_rules(self, mock_project_cache, mock_label_cache):
        """Test that empty rules don't ignore anything."""
        rules = IgnoreRules()
        
        service = TaskIgnoreService(
            project_cache=mock_project_cache,
            label_cache=mock_label_cache,
            ignore_rules=rules
        )
        
        task_json = {
            "project_id": "any_project",
            "labels": ["any_label"]
        }
        
        assert service.should_ignore(task_json) is False