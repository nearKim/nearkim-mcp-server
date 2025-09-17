"""Tests for Todoist application services."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.adapters.todoist.dto import (
    LabelCacheDTO,
    LabelDTO,
    Priority,
    ProjectCacheDTO,
    ProjectDTO,
    TaskDTO,
    TaskUpdateDTO,
)
from src.application.service.todoist import (
    CacheService,
    ClassificationService,
    LabelService,
    TaskIgnoreService,
    TaskService,
    TodoistService,
)
from src.domain.models import ClassificationDecision, DecisionStatus
from src.domain.services.task_ignore import IgnoreRules


class TestCacheService:
    """Test CacheService."""
    
    def test_initial_state(self):
        """Test cache service initial state."""
        cache = CacheService()
        
        assert isinstance(cache.labels, LabelCacheDTO)
        assert isinstance(cache.projects, ProjectCacheDTO)
        assert cache.is_labels_cached() is False
        assert cache.is_projects_cached() is False
    
    def test_populate_labels(self):
        """Test populating label cache."""
        cache = CacheService()
        
        labels = [
            LabelDTO(id="1", name="urgent", color="red", order=1, is_favorite=False),
            LabelDTO(id="2", name="important", color="blue", order=2, is_favorite=True),
        ]
        
        cache.populate_labels(labels)
        
        assert cache.is_labels_cached() is True
        assert cache.labels.get_id("urgent") == "1"
        assert cache.labels.get_id("important") == "2"
    
    def test_populate_projects(self):
        """Test populating project cache."""
        cache = CacheService()
        
        projects = [
            ProjectDTO(id="p1", name="Work", parent_id=None, order=1, color="grey", is_favorite=True),
            ProjectDTO(id="p2", name="Personal", parent_id=None, order=2, color="blue", is_favorite=False),
        ]
        
        cache.populate_projects(projects)
        
        assert cache.is_projects_cached() is True
        assert cache.projects.get_name("p1") == "Work"
        assert cache.projects.get_name("p2") == "Personal"
    
    def test_clear_cache(self):
        """Test clearing all caches."""
        cache = CacheService()
        
        # Populate caches
        cache.populate_labels([
            LabelDTO(id="1", name="test", color="red", order=1, is_favorite=False)
        ])
        cache.populate_projects([
            ProjectDTO(id="p1", name="Test", parent_id=None, order=1, color="grey", is_favorite=False)
        ])
        
        # Clear
        cache.clear()
        
        assert cache.is_labels_cached() is False
        assert cache.is_projects_cached() is False
        assert cache.labels.get_id("test") is None
        assert cache.projects.get_name("p1") is None


class TestTaskService:
    """Test TaskService."""
    
    @pytest.mark.asyncio
    async def test_get_task(self):
        """Test getting a task."""
        mock_api = AsyncMock()
        expected_task = TaskDTO(
            id="123",
            content="Test task",
            description="Description",
            project_id="p1",
            labels=["work"],
            priority=2
        )
        mock_api.get_task.return_value = expected_task
        
        service = TaskService(mock_api)
        result = await service.get_task("123")
        
        assert result == expected_task
        mock_api.get_task.assert_called_once_with("123")
    
    @pytest.mark.asyncio
    async def test_update_task(self):
        """Test updating a task."""
        mock_api = AsyncMock()
        service = TaskService(mock_api)
        
        update = TaskUpdateDTO(content="Updated", priority=1)
        await service.update_task("456", update)
        
        mock_api.update_task.assert_called_once_with(
            "456",
            content="Updated",
            priority=1
        )
    
    @pytest.mark.asyncio
    async def test_set_priority(self):
        """Test setting task priority."""
        mock_api = AsyncMock()
        service = TaskService(mock_api)
        
        await service.set_priority("789", 3)
        
        mock_api.update_task.assert_called_once_with("789", priority=3)
    
    @pytest.mark.asyncio
    async def test_merge_and_update_labels(self):
        """Test merging and updating labels."""
        mock_api = AsyncMock()
        
        # Existing task with labels
        existing_task = TaskDTO(
            id="111",
            content="Task",
            project_id="p1",
            labels=["existing", "label"]
        )
        mock_api.get_task.return_value = existing_task
        
        service = TaskService(mock_api)
        
        # Add new labels
        await service.merge_and_update_labels("111", ["@new", "label"])
        
        # Verify merge (should have: existing, label, new)
        mock_api.update_task.assert_called_once()
        call_args = mock_api.update_task.call_args
        assert call_args[0][0] == "111"
        labels = call_args[1]["labels"]
        assert set(labels) == {"existing", "label", "new"}
    
    @pytest.mark.asyncio
    async def test_merge_labels_no_change(self):
        """Test that no update occurs when labels haven't changed."""
        mock_api = AsyncMock()
        
        existing_task = TaskDTO(
            id="222",
            content="Task",
            project_id="p1",
            labels=["work", "urgent"]
        )
        mock_api.get_task.return_value = existing_task
        
        service = TaskService(mock_api)
        
        # Try to add existing labels
        await service.merge_and_update_labels("222", ["work", "@urgent"])
        
        # Should not call update
        mock_api.update_task.assert_not_called()


class TestLabelService:
    """Test LabelService."""
    
    @pytest.mark.asyncio
    async def test_ensure_cache_loaded(self):
        """Test ensuring label cache is loaded."""
        mock_api = AsyncMock()
        mock_cache = MagicMock()
        
        labels = [
            LabelDTO(id="1", name="test", color="red", order=1, is_favorite=False)
        ]
        mock_api.fetch_labels.return_value = labels
        mock_cache.is_labels_cached.return_value = False
        
        service = LabelService(mock_api, mock_cache)
        await service.ensure_cache_loaded()
        
        mock_api.fetch_labels.assert_called_once()
        mock_cache.populate_labels.assert_called_once_with(labels)
    
    @pytest.mark.asyncio
    async def test_ensure_labels_exist_with_autocreate(self):
        """Test ensuring labels exist with autocreate enabled."""
        mock_api = AsyncMock()
        mock_cache = MagicMock()
        
        # Setup cache
        mock_cache.is_labels_cached.return_value = True
        mock_cache.labels.get_id.side_effect = lambda name: {
            "existing": "id1"
        }.get(name)
        
        # New label creation
        new_label = LabelDTO(id="id2", name="new", color="blue", order=2, is_favorite=False)
        mock_api.add_label.return_value = new_label
        
        service = LabelService(mock_api, mock_cache, autocreate=True)
        
        result = await service.ensure_labels_exist(["existing", "@new"])
        
        assert result == {"existing": "id1", "@new": "id2"}
        mock_api.add_label.assert_called_once_with("new")
        mock_cache.labels.add.assert_called_once_with(new_label)
    
    @pytest.mark.asyncio
    async def test_ensure_labels_without_autocreate(self):
        """Test ensuring labels without autocreate."""
        mock_api = AsyncMock()
        mock_cache = MagicMock()
        
        mock_cache.is_labels_cached.return_value = True
        mock_cache.labels.get_id.side_effect = lambda name: {
            "existing": "id1"
        }.get(name)
        
        service = LabelService(mock_api, mock_cache, autocreate=False)
        
        result = await service.ensure_labels_exist(["existing", "@nonexistent"])
        
        assert result == {"existing": "id1"}
        mock_api.add_label.assert_not_called()


class TestClassificationService:
    """Test ClassificationService."""
    
    @pytest.mark.asyncio
    async def test_apply_eisenhower_as_labels(self):
        """Test applying Eisenhower classification as labels."""
        mock_task_service = AsyncMock()
        mock_label_service = AsyncMock()
        
        mock_label_service.ensure_labels_exist.return_value = {
            "urgent": "u1",
            "important": "i1"
        }
        
        service = ClassificationService(mock_task_service, mock_label_service)
        
        decision = ClassificationDecision(
            quadrant="Q1",
            urgent=True,
            important=True,
            reason="Test"
        )
        
        await service.apply_eisenhower_as_labels(
            "task123",
            decision,
            "urgent",
            "important"
        )
        
        mock_label_service.ensure_labels_exist.assert_called_once_with(["urgent", "important"])
        mock_task_service.merge_and_update_labels.assert_called_once_with(
            "task123",
            ["urgent", "important"]
        )
    
    @pytest.mark.asyncio
    async def test_apply_eisenhower_as_priority(self):
        """Test applying Eisenhower classification as priority."""
        mock_task_service = AsyncMock()
        mock_label_service = AsyncMock()
        
        service = ClassificationService(mock_task_service, mock_label_service)
        
        # Test each quadrant mapping
        test_cases = [
            ("Q1", Priority.P1.value),  # Urgent & Important
            ("Q2", Priority.P2.value),  # Important, not Urgent
            ("Q3", Priority.P3.value),  # Urgent, not Important
            ("Q4", Priority.P4.value),  # Neither
        ]
        
        for quadrant, expected_priority in test_cases:
            decision = ClassificationDecision(
                quadrant=quadrant,
                urgent=(quadrant in ["Q1", "Q3"]),
                important=(quadrant in ["Q1", "Q2"]),
                reason="Test"
            )
            
            await service.apply_eisenhower_as_priority("task456", decision)
            
            mock_task_service.set_priority.assert_called_with("task456", expected_priority)


class TestTaskIgnoreService:
    """Test TaskIgnoreService."""
    
    @pytest.mark.asyncio
    async def test_ensure_caches_loaded(self):
        """Test ensuring both caches are loaded."""
        mock_cache = MagicMock()
        mock_api = AsyncMock()
        
        mock_cache.is_labels_cached.return_value = False
        mock_cache.is_projects_cached.return_value = False
        
        labels = [LabelDTO(id="1", name="test", color="red", order=1, is_favorite=False)]
        projects = [ProjectDTO(id="p1", name="Test", parent_id=None, order=1, color="grey", is_favorite=False)]
        
        mock_api.fetch_labels.return_value = labels
        mock_api.fetch_projects.return_value = projects
        
        rules = IgnoreRules()
        service = TaskIgnoreService(mock_cache, mock_api, rules)
        
        await service.ensure_caches_loaded()
        
        mock_api.fetch_labels.assert_called_once()
        mock_api.fetch_projects.assert_called_once()
        mock_cache.populate_labels.assert_called_once_with(labels)
        mock_cache.populate_projects.assert_called_once_with(projects)
    
    @pytest.mark.asyncio
    async def test_should_ignore_delegates_to_domain(self):
        """Test that should_ignore delegates to domain service."""
        mock_cache = MagicMock()
        mock_api = AsyncMock()
        
        mock_cache.is_labels_cached.return_value = True
        mock_cache.is_projects_cached.return_value = True
        
        rules = IgnoreRules(project_ids={"proj_ignore"})
        
        with patch('src.application.service.todoist.task_ignore.DomainTaskIgnoreService') as MockDomainService:
            mock_domain_service = MagicMock()
            mock_domain_service.should_ignore.return_value = True
            MockDomainService.return_value = mock_domain_service
            
            service = TaskIgnoreService(mock_cache, mock_api, rules)
            
            task_json = {"project_id": "proj_ignore", "labels": []}
            result = await service.should_ignore(task_json)
            
            assert result is True
            mock_domain_service.should_ignore.assert_called_once_with(task_json)


class TestTodoistService:
    """Test TodoistService batch operations."""
    
    @pytest.mark.asyncio
    async def test_classify_all_tasks_success(self):
        """Test successful batch classification of tasks."""
        mock_adapter = AsyncMock()
        mock_classifier = MagicMock()
        mock_ignore_service = MagicMock()
        mock_decision_repo = AsyncMock()
        mock_calendar_service = AsyncMock()
        
        mock_adapter.fetch_tasks.return_value = [
            {
                "id": "task1",
                "content": "Important task",
                "project_id": "proj1",
                "labels": ["work"],
                "priority": 4,
                "due": None
            },
            {
                "id": "task2",
                "content": "Urgent task",
                "project_id": "proj1",
                "labels": [],
                "priority": 1,
                "due": {"date": "2024-01-20"}
            },
            {
                "id": "task3",
                "content": "Ignored task",
                "project_id": "ignored_proj",
                "labels": ["no-eisenhower"],
                "priority": 1,
                "due": None
            }
        ]
        
        mock_ignore_service.should_ignore.side_effect = [False, False, True]
        
        decision1 = ClassificationDecision(
            quadrant="Q2",
            urgent=False,
            important=True,
            reason="Important but not urgent"
        )
        decision2 = ClassificationDecision(
            quadrant="Q1",
            urgent=True,
            important=True,
            reason="Urgent and important"
        )
        mock_classifier.classify.side_effect = [decision1, decision2]
        
        mock_calendar_service.schedule_q2_task.return_value = {
            "event_id": "cal123",
            "start": "2024-01-15T10:00:00Z",
            "end": "2024-01-15T11:30:00Z"
        }
        
        service = TodoistService(
            adapter=mock_adapter,
            classifier=mock_classifier,
            ignore_service=mock_ignore_service,
            decision_repository=mock_decision_repo,
            calendar_service=mock_calendar_service
        )
        
        result = await service.classify_all_tasks(project_id="proj1")
        
        assert result["total"] == 3
        assert result["classified"] == 2
        assert result["ignored"] == 1
        assert result["failed"] == 0
        assert result["q2_scheduled"] == 1
        
        assert mock_adapter.fetch_tasks.called_once_with(project_id="proj1")
        assert mock_classifier.classify.call_count == 2
        assert mock_adapter.apply_eisenhower.call_count == 2
        assert mock_decision_repo.save_decision.call_count == 2
        assert mock_calendar_service.schedule_q2_task.call_count == 1
    
    @pytest.mark.asyncio
    async def test_classify_all_tasks_with_errors(self):
        """Test batch classification with some errors."""
        mock_adapter = AsyncMock()
        mock_classifier = MagicMock()
        mock_ignore_service = MagicMock()
        mock_decision_repo = AsyncMock()
        
        mock_adapter.fetch_tasks.return_value = [
            {
                "id": "task1",
                "content": "Good task",
                "project_id": "proj1",
                "labels": [],
                "priority": 2,
                "due": None
            },
            {
                "id": "task2",
                "content": "Bad task",
                "project_id": "proj1",
                "labels": [],
                "priority": 2,
                "due": None
            }
        ]
        
        mock_ignore_service.should_ignore.return_value = False
        
        decision1 = ClassificationDecision(
            quadrant="Q3",
            urgent=True,
            important=False,
            reason="Urgent but not important"
        )
        mock_classifier.classify.side_effect = [
            decision1,
            Exception("Classification failed")
        ]
        
        service = TodoistService(
            adapter=mock_adapter,
            classifier=mock_classifier,
            ignore_service=mock_ignore_service,
            decision_repository=mock_decision_repo,
            calendar_service=None
        )
        
        result = await service.classify_all_tasks()
        
        assert result["total"] == 2
        assert result["classified"] == 1
        assert result["ignored"] == 0
        assert result["failed"] == 1
        assert result["q2_scheduled"] == 0
    
    @pytest.mark.asyncio
    async def test_fetch_tasks_with_project_filter(self):
        """Test fetch_tasks with project filtering."""
        from src.adapters.todoist.adapter import TodoistAPIAdapter
        from todoist_api_python.api_async import TodoistAPIAsync
        from todoist_api_python.models import Task
        
        mock_api = AsyncMock(spec=TodoistAPIAsync)
        api_adapter = TodoistAPIAdapter(mock_api)
        
        mock_task1 = MagicMock(spec=Task)
        mock_task1.id = "task1"
        mock_task1.content = "Task in project"
        mock_task1.project_id = "proj123"
        mock_task1.labels = ["urgent"]
        mock_task1.priority = 4
        mock_task1.due = None
        
        async def mock_get_tasks_generator(project_id=None):
            yield [mock_task1]
        
        mock_api.get_tasks.return_value = mock_get_tasks_generator(project_id="proj123")
        
        result = await api_adapter.fetch_tasks(project_id="proj123")
        
        assert len(result) == 1
        assert result[0]["id"] == "task1"
        assert result[0]["content"] == "Task in project"
        assert result[0]["project_id"] == "proj123"
        assert result[0]["labels"] == ["urgent"]
        assert result[0]["priority"] == 4
        assert result[0]["due"] is None
        
        mock_api.get_tasks.assert_called_once_with(project_id="proj123")