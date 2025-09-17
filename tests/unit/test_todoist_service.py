"""Comprehensive unit tests for TodoistService."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, call
from typing import List

from src.application.service.todoist_service import TodoistService
from src.domain.entities import Task
from src.domain.models import ClassificationDecision, DecisionRecord
from src.ports.todoist import TodoistPort
from src.domain.services.classification import ClassifierService
from src.domain.services.task_ignore import TaskIgnoreService
from src.domain.repositories import DecisionRepository


class TestTodoistService:
    """Test TodoistService with mocked dependencies."""

    @pytest.fixture
    def mock_adapter(self):
        """Create a mock TodoistPort adapter."""
        adapter = AsyncMock(spec=TodoistPort)
        return adapter

    @pytest.fixture
    def mock_classifier(self):
        """Create a mock ClassifierService."""
        classifier = AsyncMock(spec=ClassifierService)
        return classifier

    @pytest.fixture
    def mock_ignore_service(self):
        """Create a mock TaskIgnoreService."""
        service = MagicMock(spec=TaskIgnoreService)
        return service

    @pytest.fixture
    def mock_decision_repo(self):
        """Create a mock DecisionRepository."""
        repo = AsyncMock(spec=DecisionRepository)
        return repo

    @pytest.fixture
    def mock_calendar_service(self):
        """Create a mock CalendarService."""
        service = AsyncMock()
        return service

    @pytest.fixture
    def todoist_service(
        self, 
        mock_adapter, 
        mock_classifier, 
        mock_ignore_service, 
        mock_decision_repo,
        mock_calendar_service
    ):
        """Create TodoistService with all mocked dependencies."""
        return TodoistService(
            adapter=mock_adapter,
            classifier=mock_classifier,
            ignore_service=mock_ignore_service,
            decision_repository=mock_decision_repo,
            calendar_service=mock_calendar_service
        )

    @pytest.fixture
    def sample_tasks(self) -> List[Task]:
        """Create sample tasks for testing."""
        return [
            Task(
                todoist_id="task1",
                content="Urgent important task",
                project_id="proj1",
                labels=[],
                priority=4,
                due={"date": "2024-03-15"}
            ),
            Task(
                todoist_id="task2",
                content="Important but not urgent",
                project_id="proj1",
                labels=[],
                priority=3,
                due=None
            ),
            Task(
                todoist_id="task3",
                content="Should be ignored",
                project_id="ignore_proj",
                labels=["ignore"],
                priority=1,
                due=None
            ),
        ]

    @pytest.mark.asyncio
    async def test_classify_all_tasks_success_path(
        self,
        todoist_service,
        mock_adapter,
        mock_classifier,
        mock_decision_repo,
        mock_calendar_service,
        sample_tasks
    ):
        """Test successful classification of all tasks."""
        # Setup
        mock_adapter.fetch_tasks.return_value = sample_tasks
        mock_adapter.should_ignore_task.side_effect = [False, False, True]  # Third task ignored
        
        decision1 = ClassificationDecision(
            quadrant="Q1",
            urgent=True,
            important=True,
            reason="Urgent and important"
        )
        decision2 = ClassificationDecision(
            quadrant="Q3",  # Changed to Q3 to avoid calendar scheduling
            urgent=True,
            important=False,
            reason="Urgent but not important"
        )
        mock_classifier.classify.side_effect = [decision1, decision2]
        
        # Mock calendar service to return None (no scheduling)
        mock_calendar_service.schedule_q2_task.return_value = None
        
        # Execute
        result = await todoist_service.classify_all_tasks(project_id="proj1")
        
        # Assert
        assert result["total"] == 3
        assert result["classified"] == 2
        assert result["ignored"] == 1
        assert result["failed"] == 0
        assert result["q2_scheduled"] == 0  # No Q2 tasks in this test
        
        # Verify calls
        mock_adapter.fetch_tasks.assert_called_once_with(project_id="proj1")
        assert mock_adapter.should_ignore_task.call_count == 3
        assert mock_classifier.classify.call_count == 2
        assert mock_adapter.apply_eisenhower.call_count == 2
        assert mock_decision_repo.save.call_count == 2

    @pytest.mark.asyncio
    async def test_classify_all_tasks_with_q2_scheduling(
        self,
        todoist_service,
        mock_adapter,
        mock_classifier,
        mock_decision_repo,
        mock_calendar_service,
        sample_tasks
    ):
        """Test Q2 task scheduling during classification."""
        # Setup - only use one Q2 task
        q2_task = sample_tasks[1]
        mock_adapter.fetch_tasks.return_value = [q2_task]
        mock_adapter.should_ignore_task.return_value = False
        
        q2_decision = ClassificationDecision(
            quadrant="Q2",
            urgent=False,
            important=True,
            reason="Schedule for deep work"
        )
        mock_classifier.classify.return_value = q2_decision
        
        mock_calendar_service.schedule_q2_task.return_value = {
            "event_id": "cal123",
            "start": "2024-03-20T10:00:00Z",
            "end": "2024-03-20T11:30:00Z"
        }
        
        # Execute
        result = await todoist_service.classify_all_tasks()
        
        # Assert
        assert result["total"] == 1
        assert result["classified"] == 1
        assert result["q2_scheduled"] == 1
        
        # Verify calendar scheduling was called
        mock_calendar_service.schedule_q2_task.assert_called_once_with(
            task_id="task2",
            task_content="Important but not urgent",
            min_block_minutes=90
        )

    @pytest.mark.asyncio
    async def test_classify_all_tasks_with_errors(
        self,
        todoist_service,
        mock_adapter,
        mock_classifier,
        sample_tasks
    ):
        """Test error handling during classification."""
        # Setup
        mock_adapter.fetch_tasks.return_value = sample_tasks[:2]
        mock_adapter.should_ignore_task.return_value = False
        
        # First task succeeds, second fails
        decision1 = ClassificationDecision(
            quadrant="Q3",
            urgent=True,
            important=False,
            reason="Delegate if possible"
        )
        mock_classifier.classify.side_effect = [
            decision1,
            Exception("Classification API error")
        ]
        
        # Execute
        result = await todoist_service.classify_all_tasks()
        
        # Assert
        assert result["total"] == 2
        assert result["classified"] == 1
        assert result["ignored"] == 0
        assert result["failed"] == 1
        
        # First task should be processed successfully
        assert mock_adapter.apply_eisenhower.call_count == 1

    @pytest.mark.asyncio
    async def test_classify_all_tasks_all_ignored(
        self,
        todoist_service,
        mock_adapter,
        mock_classifier,
        sample_tasks
    ):
        """Test when all tasks are ignored."""
        # Setup
        mock_adapter.fetch_tasks.return_value = sample_tasks
        mock_adapter.should_ignore_task.return_value = True  # All tasks ignored
        
        # Execute
        result = await todoist_service.classify_all_tasks()
        
        # Assert
        assert result["total"] == 3
        assert result["classified"] == 0
        assert result["ignored"] == 3
        assert result["failed"] == 0
        
        # Classifier should never be called
        mock_classifier.classify.assert_not_called()
        mock_adapter.apply_eisenhower.assert_not_called()

    @pytest.mark.asyncio
    async def test_reclassify_task_success(
        self,
        todoist_service,
        mock_adapter,
        mock_classifier,
        mock_decision_repo
    ):
        """Test successful task reclassification."""
        # Setup
        task = Task(
            todoist_id="task123",
            content="Reclassify me",
            project_id="proj1",
            labels=["old_label"],
            priority=2,
            due=None
        )
        mock_adapter.get_task.return_value = task
        
        new_decision = ClassificationDecision(
            quadrant="Q1",
            urgent=True,
            important=True,
            reason="Actually urgent now"
        )
        mock_classifier.classify.return_value = new_decision
        
        # Execute
        result = await todoist_service.reclassify_task("task123")
        
        # Assert
        assert result == new_decision
        
        # Verify calls
        mock_adapter.get_task.assert_called_once_with("task123")
        mock_classifier.classify.assert_called_once_with(task, force_json=True)
        mock_adapter.apply_eisenhower.assert_called_once_with("task123", new_decision)
        
        # Verify decision was saved
        assert mock_decision_repo.save.call_count == 1
        saved_record = mock_decision_repo.save.call_args[0][0]
        assert isinstance(saved_record, DecisionRecord)

    @pytest.mark.asyncio
    async def test_reclassify_task_with_q2_scheduling(
        self,
        todoist_service,
        mock_adapter,
        mock_classifier,
        mock_calendar_service
    ):
        """Test reclassification with Q2 scheduling."""
        # Setup
        task = Task(
            todoist_id="task456",
            content="Now important",
            project_id="proj2",
            labels=[],
            priority=3,
            due=None
        )
        mock_adapter.get_task.return_value = task
        
        q2_decision = ClassificationDecision(
            quadrant="Q2",
            urgent=False,
            important=True,
            reason="Schedule for next week"
        )
        mock_classifier.classify.return_value = q2_decision
        
        mock_calendar_service.schedule_q2_task.return_value = {
            "event_id": "cal456",
            "start": "2024-03-25T14:00:00Z",
            "end": "2024-03-25T15:30:00Z"
        }
        
        # Execute
        result = await todoist_service.reclassify_task("task456")
        
        # Assert
        assert result.quadrant == "Q2"
        
        # Verify calendar scheduling
        mock_calendar_service.schedule_q2_task.assert_called_once_with(
            task_id="task456",
            task_content="Now important",
            min_block_minutes=90
        )

    @pytest.mark.asyncio
    async def test_get_quadrant_tasks(
        self,
        todoist_service,
        mock_adapter,
        mock_decision_repo
    ):
        """Test fetching tasks by quadrant."""
        # Setup
        decisions = [
            MagicMock(todoist_id="task1", quadrant="Q1", reason="Urgent"),
            MagicMock(todoist_id="task2", quadrant="Q1", reason="Also urgent"),
        ]
        mock_decision_repo.get_by_quadrant.return_value = decisions
        
        task1 = Task(
            todoist_id="task1",
            content="First Q1 task",
            project_id="proj1",
            labels=["Q1"],
            priority=4,
            due={"date": "2024-03-15"}
        )
        task2 = Task(
            todoist_id="task2",
            content="Second Q1 task",
            project_id="proj1",
            labels=["Q1"],
            priority=4,
            due=None
        )
        mock_adapter.get_task.side_effect = [task1, task2]
        
        # Execute
        result = await todoist_service.get_quadrant_tasks("Q1")
        
        # Assert
        assert len(result) == 2
        assert result[0]["id"] == "task1"
        assert result[0]["content"] == "First Q1 task"
        assert result[0]["quadrant"] == "Q1"
        assert result[0]["reason"] == "Urgent"
        assert result[0]["due"] == {"date": "2024-03-15"}
        
        assert result[1]["id"] == "task2"
        assert result[1]["content"] == "Second Q1 task"
        
        # Verify calls
        mock_decision_repo.get_by_quadrant.assert_called_once_with("Q1")
        assert mock_adapter.get_task.call_count == 2

    @pytest.mark.asyncio
    async def test_get_quadrant_tasks_with_fetch_error(
        self,
        todoist_service,
        mock_adapter,
        mock_decision_repo
    ):
        """Test handling of fetch errors when getting quadrant tasks."""
        # Setup
        decisions = [
            MagicMock(todoist_id="task1", quadrant="Q2", reason="Important"),
            MagicMock(todoist_id="task2", quadrant="Q2", reason="Also important"),
            MagicMock(todoist_id="task3", quadrant="Q2", reason="Very important"),
        ]
        mock_decision_repo.get_by_quadrant.return_value = decisions
        
        task1 = Task(
            todoist_id="task1",
            content="Valid task",
            project_id="proj1",
            labels=["Q2"],
            priority=3,
            due=None
        )
        
        # First task succeeds, second fails, third succeeds
        task3 = Task(
            todoist_id="task3",
            content="Another valid task",
            project_id="proj1",
            labels=["Q2"],
            priority=3,
            due=None
        )
        
        mock_adapter.get_task.side_effect = [
            task1,
            Exception("Task deleted"),
            task3
        ]
        
        # Execute
        result = await todoist_service.get_quadrant_tasks("Q2")
        
        # Assert - should skip the failed task
        assert len(result) == 2
        assert result[0]["id"] == "task1"
        assert result[1]["id"] == "task3"
        
        # All three fetches should be attempted
        assert mock_adapter.get_task.call_count == 3

    @pytest.mark.asyncio
    async def test_classify_without_calendar_service(
        self,
        mock_adapter,
        mock_classifier,
        mock_ignore_service,
        mock_decision_repo
    ):
        """Test classification when calendar service is None."""
        # Create service without calendar
        service = TodoistService(
            adapter=mock_adapter,
            classifier=mock_classifier,
            ignore_service=mock_ignore_service,
            decision_repository=mock_decision_repo,
            calendar_service=None  # No calendar service
        )
        
        # Setup
        q2_task = Task(
            todoist_id="q2_task",
            content="Q2 without calendar",
            project_id="proj1",
            labels=[],
            priority=3,
            due=None
        )
        mock_adapter.fetch_tasks.return_value = [q2_task]
        mock_adapter.should_ignore_task.return_value = False
        
        q2_decision = ClassificationDecision(
            quadrant="Q2",
            urgent=False,
            important=True,
            reason="Important task"
        )
        mock_classifier.classify.return_value = q2_decision
        
        # Execute
        result = await service.classify_all_tasks()
        
        # Assert - should work but no scheduling
        assert result["total"] == 1
        assert result["classified"] == 1
        assert result["q2_scheduled"] == 0  # No scheduling without calendar

    @pytest.mark.asyncio
    async def test_schedule_q2_task_calendar_error(
        self,
        todoist_service,
        mock_adapter,
        mock_classifier,
        mock_calendar_service
    ):
        """Test handling of calendar scheduling errors."""
        # Setup
        task = Task(
            todoist_id="task789",
            content="Q2 task with calendar error",
            project_id="proj1",
            labels=[],
            priority=3,
            due=None
        )
        mock_adapter.fetch_tasks.return_value = [task]
        mock_adapter.should_ignore_task.return_value = False
        
        q2_decision = ClassificationDecision(
            quadrant="Q2",
            urgent=False,
            important=True,
            reason="Try to schedule"
        )
        mock_classifier.classify.return_value = q2_decision
        
        # Calendar service raises error
        mock_calendar_service.schedule_q2_task.side_effect = Exception("Calendar API error")
        
        # Execute
        result = await todoist_service.classify_all_tasks()
        
        # Assert - classification should succeed despite calendar error
        assert result["total"] == 1
        assert result["classified"] == 1
        assert result["q2_scheduled"] == 0  # Failed to schedule
        assert result["failed"] == 0  # But classification itself succeeded

    @pytest.mark.asyncio
    async def test_decision_repository_integration(
        self,
        todoist_service,
        mock_adapter,
        mock_classifier,
        mock_decision_repo
    ):
        """Test that decisions are properly saved to repository."""
        # Setup
        task = Task(
            todoist_id="repo_test",
            content="Test repository save",
            project_id="proj1",
            labels=[],
            priority=2,
            due=None
        )
        mock_adapter.fetch_tasks.return_value = [task]
        mock_adapter.should_ignore_task.return_value = False
        
        decision = ClassificationDecision(
            quadrant="Q3",
            urgent=True,
            important=False,
            reason="Delegate"
        )
        mock_classifier.classify.return_value = decision
        
        # Execute
        await todoist_service.classify_all_tasks()
        
        # Verify the decision record was created and saved
        mock_decision_repo.save.assert_called_once()
        saved_record = mock_decision_repo.save.call_args[0][0]
        
        assert isinstance(saved_record, DecisionRecord)
        # DecisionRecord should be created from the decision
        assert saved_record.todoist_id == "repo_test"
        assert saved_record.quadrant == "Q3"
        assert saved_record.applied_mode == "labels"