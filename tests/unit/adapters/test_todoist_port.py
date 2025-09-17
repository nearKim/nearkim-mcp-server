from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict

from src.adapters.todoist_simple import TodoistAdapter
from src.domain.entities import Task
from src.domain.models import ClassificationDecision
from src.domain.services.task_ignore import TaskIgnoreService
from src.ports.todoist import TodoistPort


class TestTodoistAdapterPortCompliance:
    """Test that TodoistAdapter properly implements TodoistPort interface."""

    def test_adapter_implements_port(self):
        """Test that TodoistAdapter is a subclass of TodoistPort."""
        assert issubclass(TodoistAdapter, TodoistPort)

    @pytest.mark.asyncio
    async def test_get_task_returns_domain_task(self):
        """Test that get_task returns a domain Task object, not a dict or DTO."""
        adapter = TodoistAdapter(api_key="test_key")
        
        # Mock the HTTP response
        mock_response = {
            "id": "123",
            "content": "Test task",
            "project_id": "proj_456",
            "labels": ["urgent", "important"],
            "priority": 4,
            "due": {"date": "2024-03-15"}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.return_value.json.return_value = mock_response
            mock_client.return_value.__aenter__.return_value.get.return_value.raise_for_status = MagicMock()
            
            result = await adapter.get_task("123")
            
            # Verify it returns a Task domain object
            assert isinstance(result, Task)
            assert result.todoist_id == "123"
            assert result.content == "Test task"
            assert result.project_id == "proj_456"
            assert result.labels == ["urgent", "important"]
            assert result.priority == 4
            assert result.due == {"date": "2024-03-15"}

    @pytest.mark.asyncio
    async def test_fetch_tasks_returns_domain_tasks(self):
        """Test that fetch_tasks returns a list of domain Task objects."""
        adapter = TodoistAdapter(api_key="test_key")
        
        # Mock the HTTP response
        mock_response = [
            {
                "id": "task1",
                "content": "First task",
                "project_id": "proj1",
                "labels": ["Q1"],
                "priority": 1,
                "due": None
            },
            {
                "id": "task2",
                "content": "Second task",
                "project_id": "proj1",
                "labels": ["Q2"],
                "priority": 2,
                "due": {"date": "2024-03-20"}
            }
        ]
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.return_value.json.return_value = mock_response
            mock_client.return_value.__aenter__.return_value.get.return_value.raise_for_status = MagicMock()
            
            results = await adapter.fetch_tasks(project_id="proj1")
            
            # Verify it returns a list of Task domain objects
            assert isinstance(results, list)
            assert len(results) == 2
            assert all(isinstance(task, Task) for task in results)
            
            assert results[0].todoist_id == "task1"
            assert results[0].content == "First task"
            assert results[0].labels == ["Q1"]
            
            assert results[1].todoist_id == "task2"
            assert results[1].content == "Second task"
            assert results[1].due == {"date": "2024-03-20"}

    @pytest.mark.asyncio
    async def test_should_ignore_task_accepts_domain_task(self):
        """Test that should_ignore_task accepts a Task domain object."""
        mock_ignore_service = MagicMock(spec=TaskIgnoreService)
        mock_ignore_service.should_ignore.return_value = False
        
        adapter = TodoistAdapter(api_key="test_key", ignore_service=mock_ignore_service)
        
        # Create a domain Task object
        task = Task(
            todoist_id="789",
            content="Test task",
            project_id="proj_999",
            labels=["label1"],
            priority=3,
            due=None
        )
        
        result = await adapter.should_ignore_task(task)
        
        # Verify the ignore service was called with the right dict structure
        mock_ignore_service.should_ignore.assert_called_once()
        call_args = mock_ignore_service.should_ignore.call_args[0][0]
        assert call_args["id"] == "789"
        assert call_args["content"] == "Test task"
        assert call_args["project_id"] == "proj_999"
        assert call_args["labels"] == ["label1"]
        assert call_args["priority"] == 3
        assert call_args["due"] is None
        
        assert result is False

    @pytest.mark.asyncio
    async def test_should_ignore_task_without_service(self):
        """Test that should_ignore_task returns False when no ignore service is configured."""
        adapter = TodoistAdapter(api_key="test_key", ignore_service=None)
        
        task = Task(
            todoist_id="test",
            content="Any task",
            project_id="any",
            labels=[],
            priority=1,
            due=None
        )
        
        result = await adapter.should_ignore_task(task)
        assert result is False

    @pytest.mark.asyncio
    async def test_apply_eisenhower_with_task_id(self):
        """Test that apply_eisenhower works with task_id and decision."""
        adapter = TodoistAdapter(api_key="test_key")
        
        decision = ClassificationDecision(
            quadrant="Q1",
            urgent=True,
            important=True,
            reason="Urgent and important task"
        )
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock()
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            await adapter.apply_eisenhower("task_123", decision)
            
            # Verify the update was called with correct labels
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]["json"]["labels"] == ["urgent", "important", "Q1"]

    @pytest.mark.asyncio
    async def test_apply_eisenhower_q2_task(self):
        """Test apply_eisenhower for Q2 task (important but not urgent)."""
        adapter = TodoistAdapter(api_key="test_key")
        
        decision = ClassificationDecision(
            quadrant="Q2",
            urgent=False,
            important=True,
            reason="Important but not urgent"
        )
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock()
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            await adapter.apply_eisenhower("task_456", decision)
            
            # Verify only important and Q2 labels are applied
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]["json"]["labels"] == ["important", "Q2"]

    @pytest.mark.asyncio
    async def test_adapter_handles_integer_task_ids(self):
        """Test that the adapter properly handles integer task IDs from API."""
        adapter = TodoistAdapter(api_key="test_key")
        
        # Mock response with integer ID (common in APIs)
        mock_response = {
            "id": 12345,  # Integer ID
            "content": "Task with integer ID",
            "project_id": None,
            "labels": None,  # Also test null labels
            "priority": 1,
            "due": None
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.return_value.json.return_value = mock_response
            mock_client.return_value.__aenter__.return_value.get.return_value.raise_for_status = MagicMock()
            
            result = await adapter.get_task("12345")
            
            # Verify it properly converts to string
            assert isinstance(result, Task)
            assert result.todoist_id == "12345"
            assert isinstance(result.todoist_id, str)
            assert result.labels == []  # null labels should become empty list