"""Tests for application middleware."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.commands.classification import ClassifyTaskCommand
from src.application.middleware.base import MiddlewarePipeline
from src.application.middleware.classification import (
    ClassificationHandler,
    FallbackMiddleware,
    ForcedJsonMiddleware,
    LoggingMiddleware,
)
from src.domain.entities import Task
from src.domain.exceptions import ClassificationException, LLMResponseFormatError
from src.domain.models import ClassificationDecision, DecisionStatus


class TestClassifyTaskCommand:
    """Test ClassifyTaskCommand."""
    
    def test_command_creation(self):
        """Test creating a classification command."""
        task = Task(todoist_id="123", content="Test", project_id="p1", labels=[])
        command = ClassifyTaskCommand(task=task, force_json=True)
        
        assert command.task == task
        assert command.force_json is True
    
    def test_command_defaults(self):
        """Test command with default values."""
        task = Task(todoist_id="456", content="Test", project_id="p2", labels=[])
        command = ClassifyTaskCommand(task=task)
        
        assert command.task == task
        assert command.force_json is False
    
    def test_command_requires_task(self):
        """Test that command requires a task."""
        with pytest.raises(ValueError, match="Task is required"):
            ClassifyTaskCommand(task=None)


class TestForcedJsonMiddleware:
    """Test ForcedJsonMiddleware."""
    
    @pytest.mark.asyncio
    async def test_successful_classification(self):
        """Test middleware passes through successful classification."""
        # Setup
        task = Task(todoist_id="123", content="Test", project_id="p1", labels=[])
        command = ClassifyTaskCommand(task=task)
        
        expected_decision = ClassificationDecision(
            quadrant="Q1",
            urgent=True,
            important=True,
            reason="Test"
        )
        
        next_handler = AsyncMock(return_value=expected_decision)
        middleware = ForcedJsonMiddleware()
        
        # Execute
        result = await middleware(command, next_handler)
        
        # Verify
        assert result == expected_decision
        assert command.force_json is False
        next_handler.assert_called_once_with(command)
    
    @pytest.mark.asyncio
    async def test_retry_with_forced_json(self):
        """Test middleware retries with forced JSON on format error."""
        # Setup
        task = Task(todoist_id="456", content="Test", project_id="p2", labels=[])
        command = ClassifyTaskCommand(task=task, force_json=False)
        
        expected_decision = ClassificationDecision(
            quadrant="Q2",
            urgent=False,
            important=True,
            reason="Retry worked"
        )
        
        # First call fails, second succeeds
        next_handler = AsyncMock(
            side_effect=[
                LLMResponseFormatError("Invalid JSON"),
                expected_decision
            ]
        )
        
        middleware = ForcedJsonMiddleware()
        
        # Execute
        result = await middleware(command, next_handler)
        
        # Verify
        assert result == expected_decision
        assert command.force_json is True
        assert next_handler.call_count == 2


class TestLoggingMiddleware:
    """Test LoggingMiddleware."""
    
    @pytest.mark.asyncio
    async def test_logs_successful_classification(self):
        """Test middleware logs successful classification."""
        # Setup
        task = Task(todoist_id="789", content="Test", project_id="p3", labels=[])
        command = ClassifyTaskCommand(task=task)
        
        expected_decision = ClassificationDecision(
            quadrant="Q3",
            urgent=True,
            important=False,
            reason="Test"
        )
        
        next_handler = AsyncMock(return_value=expected_decision)
        logger = MagicMock()
        middleware = LoggingMiddleware(logger=logger)
        
        # Execute
        result = await middleware(command, next_handler)
        
        # Verify
        assert result == expected_decision
        logger.assert_any_call("Classifying task: 789")
        logger.assert_any_call("Classification successful: Q3")
    
    @pytest.mark.asyncio
    async def test_logs_classification_failure(self):
        """Test middleware logs classification failure."""
        # Setup
        task = Task(todoist_id="999", content="Test", project_id="p4", labels=[])
        command = ClassifyTaskCommand(task=task)
        
        error = ClassificationException("Test error")
        next_handler = AsyncMock(side_effect=error)
        logger = MagicMock()
        middleware = LoggingMiddleware(logger=logger)
        
        # Execute & Verify
        with pytest.raises(ClassificationException):
            await middleware(command, next_handler)
        
        logger.assert_any_call("Classifying task: 999")
        logger.assert_any_call("Classification failed: Test error")


class TestFallbackMiddleware:
    """Test FallbackMiddleware."""
    
    @pytest.mark.asyncio
    async def test_passes_through_success(self):
        """Test middleware passes through successful classification."""
        # Setup
        task = Task(todoist_id="111", content="Test", project_id="p5", labels=[])
        command = ClassifyTaskCommand(task=task)
        
        expected_decision = ClassificationDecision(
            quadrant="Q1",
            urgent=True,
            important=True,
            reason="Success"
        )
        
        next_handler = AsyncMock(return_value=expected_decision)
        middleware = FallbackMiddleware()
        
        # Execute
        result = await middleware(command, next_handler)
        
        # Verify
        assert result == expected_decision
        assert result.status == DecisionStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_returns_fallback_on_classification_error(self):
        """Test middleware returns fallback on ClassificationException."""
        # Setup
        task = Task(todoist_id="222", content="Test", project_id="p6", labels=[])
        command = ClassifyTaskCommand(task=task)
        
        error = ClassificationException("API error")
        next_handler = AsyncMock(side_effect=error)
        middleware = FallbackMiddleware()
        
        # Execute
        result = await middleware(command, next_handler)
        
        # Verify
        assert result.quadrant == "Q4"
        assert result.urgent is False
        assert result.important is False
        assert result.status == DecisionStatus.FALLBACK
        assert "ClassificationException: API error" in result.error_detail
    
    @pytest.mark.asyncio
    async def test_returns_fallback_on_format_error(self):
        """Test middleware returns fallback on LLMResponseFormatError."""
        # Setup
        task = Task(todoist_id="333", content="Test", project_id="p7", labels=[])
        command = ClassifyTaskCommand(task=task)
        
        error = LLMResponseFormatError("Invalid JSON")
        next_handler = AsyncMock(side_effect=error)
        middleware = FallbackMiddleware()
        
        # Execute
        result = await middleware(command, next_handler)
        
        # Verify
        assert result.quadrant == "Q4"
        assert result.status == DecisionStatus.FALLBACK
        assert "LLMResponseFormatError: Invalid JSON" in result.error_detail
    
    @pytest.mark.asyncio
    async def test_handles_unexpected_error(self):
        """Test middleware handles unexpected errors."""
        # Setup
        task = Task(todoist_id="444", content="Test", project_id="p8", labels=[])
        command = ClassifyTaskCommand(task=task)
        
        error = RuntimeError("Unexpected!")
        next_handler = AsyncMock(side_effect=error)
        middleware = FallbackMiddleware()
        
        # Execute
        result = await middleware(command, next_handler)
        
        # Verify
        assert result.quadrant == "Q4"
        assert result.status == DecisionStatus.FALLBACK
        assert "Unexpected error during classification" in result.error_detail


class TestMiddlewarePipeline:
    """Test MiddlewarePipeline."""
    
    @pytest.mark.asyncio
    async def test_pipeline_execution_order(self):
        """Test middleware executes in correct order."""
        # Setup
        task = Task(todoist_id="555", content="Test", project_id="p9", labels=[])
        command = ClassifyTaskCommand(task=task)
        
        execution_log = []
        
        class LoggingMiddleware1:
            async def __call__(self, cmd, next_handler):
                execution_log.append("middleware1_before")
                result = await next_handler(cmd)
                execution_log.append("middleware1_after")
                return result
        
        class LoggingMiddleware2:
            async def __call__(self, cmd, next_handler):
                execution_log.append("middleware2_before")
                result = await next_handler(cmd)
                execution_log.append("middleware2_after")
                return result
        
        expected_decision = ClassificationDecision(
            quadrant="Q1",
            urgent=True,
            important=True,
            reason="Test"
        )
        
        async def handler(cmd):
            execution_log.append("handler")
            return expected_decision
        
        pipeline = MiddlewarePipeline(handler)
        pipeline.use(LoggingMiddleware1())
        pipeline.use(LoggingMiddleware2())
        
        # Execute
        result = await pipeline.execute(command)
        
        # Verify
        assert result == expected_decision
        assert execution_log == [
            "middleware1_before",
            "middleware2_before",
            "handler",
            "middleware2_after",
            "middleware1_after"
        ]
    
    @pytest.mark.asyncio
    async def test_empty_pipeline(self):
        """Test pipeline with no middleware."""
        # Setup
        task = Task(todoist_id="666", content="Test", project_id="p10", labels=[])
        command = ClassifyTaskCommand(task=task)
        
        expected_decision = ClassificationDecision(
            quadrant="Q2",
            urgent=False,
            important=True,
            reason="Direct"
        )
        
        async def handler(cmd):
            return expected_decision
        
        pipeline = MiddlewarePipeline(handler)
        
        # Execute
        result = await pipeline.execute(command)
        
        # Verify
        assert result == expected_decision


class TestClassificationHandler:
    """Test ClassificationHandler."""
    
    @pytest.mark.asyncio
    async def test_handler_calls_classifier(self):
        """Test handler delegates to classifier service."""
        # Setup
        task = Task(todoist_id="777", content="Test", project_id="p11", labels=[])
        command = ClassifyTaskCommand(task=task, force_json=True)
        
        expected_decision = ClassificationDecision(
            quadrant="Q3",
            urgent=True,
            important=False,
            reason="Classified"
        )
        
        mock_classifier = MagicMock()
        mock_classifier.classify = MagicMock(return_value=expected_decision)
        
        handler = ClassificationHandler(mock_classifier)
        
        # Execute
        result = await handler(command)
        
        # Verify
        assert result == expected_decision
        mock_classifier.classify.assert_called_once_with(
            task,
            force_json=True
        )