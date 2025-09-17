"""Integration tests for webhook processing flow."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.application.service.webhook import TodoistWebhookService
from src.application.dto.webhook import WebhookEventDTO, WebhookResponseDTO
from src.domain.entities import Task
from src.domain.models import ClassificationDecision, DecisionRecord, DecisionStatus
from src.domain.services.classification import ClassifierService


class TestWebhookIntegration:
    """Test complete webhook processing flow."""
    
    @pytest.mark.asyncio
    async def test_successful_classification_flow(self):
        """Test successful task classification through webhook."""
        # Setup mocks
        mock_todoist_port = AsyncMock()
        mock_classifier = MagicMock()
        mock_decisions = AsyncMock()
        
        # Configure task response
        task = Task(
            todoist_id="task_123",
            content="Complete quarterly report",
            project_id="work_proj",
            labels=[]
        )
        mock_todoist_port.get_task.return_value = task
        mock_todoist_port.should_ignore_task.return_value = False
        
        # Configure classification
        decision = ClassificationDecision(
            quadrant="Q1",
            urgent=True,
            important=True,
            reason="Deadline tomorrow, high impact",
            status=DecisionStatus.SUCCESS
        )
        mock_classifier.classify.return_value = decision
        
        # Create service
        classifier_service = ClassifierService(llm=mock_classifier)
        service = TodoistWebhookService(
            todoist_port=mock_todoist_port,
            classifier=classifier_service,
            decisions=mock_decisions,
            output_mode="labels"
        )
        
        # Execute webhook
        payload = {
            "event_data": {
                "id": "task_123",
                "content": "Complete quarterly report"
            }
        }
        
        result = await service.handle("item:added", payload)
        
        # Verify flow
        assert result.status == "applied"
        assert result.task_id == "task_123"
        assert result.decision["quadrant"] == "Q1"
        assert result.decision["urgent"] is True
        assert result.decision["important"] is True
        
        # Verify interactions
        mock_todoist_port.get_task.assert_called_once_with("task_123")
        mock_todoist_port.apply_eisenhower.assert_called_once_with("task_123", decision)
        mock_decisions.save.assert_called_once()
        
        # Check saved record
        saved_record = mock_decisions.save.call_args[0][0]
        assert isinstance(saved_record, DecisionRecord)
        assert saved_record.todoist_id == "task_123"
        assert saved_record.quadrant == "Q1"
    
    @pytest.mark.asyncio
    async def test_ignored_task_flow(self):
        """Test flow when task should be ignored."""
        # Setup
        mock_todoist_port = AsyncMock()
        mock_classifier = MagicMock()
        mock_decisions = AsyncMock()
        
        task = Task(
            todoist_id="task_456",
            content="Ignored task",
            project_id="archive_proj",
            labels=["no-eisenhower"]
        )
        mock_todoist_port.get_task.return_value = task
        mock_todoist_port.should_ignore_task.return_value = True
        
        service = TodoistWebhookService(
            todoist_port=mock_todoist_port,
            classifier=ClassifierService(llm=mock_classifier),
            decisions=mock_decisions,
            output_mode="priorities"
        )
        
        # Execute
        payload = {"event_data": {"id": "task_456"}}
        result = await service.handle("item:added", payload)
        
        # Verify
        assert result.status == "ignored"
        assert result.task_id == "task_456"
        
        mock_todoist_port.get_task.assert_called_once_with("task_456")
        mock_todoist_port.apply_eisenhower.assert_not_called()
        mock_decisions.delete.assert_called_once_with("task_456")
        mock_classifier.classify_task.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_task_completion_flow(self):
        """Test flow when task is completed."""
        # Setup
        mock_todoist_port = AsyncMock()
        mock_classifier = MagicMock()
        mock_decisions = AsyncMock()
        
        service = TodoistWebhookService(
            todoist_port=mock_todoist_port,
            classifier=ClassifierService(llm=mock_classifier),
            decisions=mock_decisions,
            output_mode="labels"
        )
        
        # Execute
        payload = {"event_data": {"id": "task_789"}}
        result = await service.handle("item:completed", payload)
        
        # Verify
        assert result.status == "completed"
        assert result.task_id == "task_789"
        
        mock_decisions.delete.assert_called_once_with("task_789")
        mock_todoist_port.get_task.assert_not_called()
        mock_classifier.classify_task.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_classification_with_fallback(self):
        """Test classification with fallback on error."""
        # Setup
        mock_todoist_port = AsyncMock()
        mock_classifier = MagicMock()
        mock_decisions = AsyncMock()
        
        task = Task(
            todoist_id="task_999",
            content="Test task",
            project_id="proj",
            labels=[]
        )
        mock_todoist_port.get_task.return_value = task
        mock_todoist_port.should_ignore_task.return_value = False
        
        # Configure classifier to fail
        from src.domain.exceptions import LLMResponseFormatError
        mock_classifier.classify.side_effect = LLMResponseFormatError("Invalid JSON")
        
        # Use middleware pipeline for proper fallback
        from src.application.middleware.base import MiddlewarePipeline
        from src.application.middleware.classification import (
            ClassificationHandler,
            FallbackMiddleware,
        )
        from src.application.commands.classification import ClassifyTaskCommand
        
        handler = ClassificationHandler(mock_classifier)
        pipeline = MiddlewarePipeline(handler)
        pipeline.use(FallbackMiddleware())
        
        # Mock the pipeline in the service
        service = TodoistWebhookService(
            todoist_port=mock_todoist_port,
            classifier=mock_classifier,
            decisions=mock_decisions,
            output_mode="labels"
        )
        service.classification_pipeline = pipeline
        
        # Execute
        payload = {"event_data": {"id": "task_999"}}
        result = await service.handle("item:added", payload)
        
        # Verify fallback was applied
        assert result.status == "fallback"
        assert result.task_id == "task_999"
        assert result.error_detail is not None
        assert "LLMResponseFormatError" in result.error_detail
        
        # Should still save decision
        mock_decisions.save.assert_called_once()
        saved_record = mock_decisions.save.call_args[0][0]
        assert saved_record.status == DecisionStatus.FALLBACK
        assert saved_record.quadrant == "Q4"
    
    @pytest.mark.asyncio
    async def test_unsupported_event(self):
        """Test handling of unsupported event types."""
        # Setup
        mock_todoist_port = AsyncMock()
        mock_classifier = MagicMock()
        mock_decisions = AsyncMock()
        
        service = TodoistWebhookService(
            todoist_port=mock_todoist_port,
            classifier=ClassifierService(llm=mock_classifier),
            decisions=mock_decisions,
            output_mode="labels"
        )
        
        # Execute with unsupported event
        payload = {"event_data": {"id": "task_000"}}
        result = await service.handle("unsupported:event", payload)
        
        # Verify
        assert result.status == "unsupported"
        assert result.event == "unsupported:event"
        assert result.reason == "unsupported_event"
        
        # No processing should occur
        mock_todoist_port.get_task.assert_not_called()
        mock_classifier.classify_task.assert_not_called()
        mock_decisions.save.assert_not_called()


class TestWebhookEventDTO:
    """Test WebhookEventDTO."""
    
    def test_from_payload_with_event_data(self):
        """Test creating event DTO from payload with event_data."""
        payload = {
            "event_data": {
                "id": "123",
                "content": "Task"
            }
        }
        
        event = WebhookEventDTO.from_payload("item:added", payload)
        
        assert event.event_name == "item:added"
        assert event.task_id == "123"
        assert event.event_data == payload
    
    def test_from_payload_with_data(self):
        """Test creating event DTO from payload with data field."""
        payload = {
            "data": {
                "id": "456"
            }
        }
        
        event = WebhookEventDTO.from_payload("item:updated", payload)
        
        assert event.task_id == "456"
    
    def test_from_payload_direct_id(self):
        """Test creating event DTO from payload with direct id."""
        payload = {
            "id": "789"
        }
        
        event = WebhookEventDTO.from_payload("item:completed", payload)
        
        assert event.task_id == "789"
    
    def test_from_payload_missing_id_raises(self):
        """Test that missing task ID raises ValueError."""
        payload = {"no_id": "here"}
        
        with pytest.raises(ValueError, match="did not contain a task identifier"):
            WebhookEventDTO.from_payload("item:added", payload)


class TestWebhookResponseDTO:
    """Test WebhookResponseDTO factory methods."""
    
    def test_applied_response(self):
        """Test creating applied response."""
        decision = ClassificationDecision(
            quadrant="Q2",
            urgent=False,
            important=True,
            reason="Important task"
        )
        
        response = WebhookResponseDTO.applied("task_1", "item:added", decision)
        
        assert response.status == "applied"
        assert response.task_id == "task_1"
        assert response.event == "item:added"
        assert response.decision["quadrant"] == "Q2"
        assert response.decision["urgent"] is False
        assert response.decision["important"] is True
    
    def test_applied_response_with_fallback(self):
        """Test creating applied response with fallback decision."""
        decision = ClassificationDecision(
            quadrant="Q4",
            urgent=False,
            important=False,
            reason="Fallback applied",
            status=DecisionStatus.FALLBACK,
            error_detail="Error occurred"
        )
        
        response = WebhookResponseDTO.applied("task_2", "item:added", decision)
        
        assert response.status == "fallback"
        assert response.error_detail == "Error occurred"
    
    def test_ignored_response(self):
        """Test creating ignored response."""
        response = WebhookResponseDTO.ignored("task_3", "item:added", "in_archive_project")
        
        assert response.status == "ignored"
        assert response.task_id == "task_3"
        assert response.reason == "in_archive_project"
    
    def test_completed_response(self):
        """Test creating completed response."""
        response = WebhookResponseDTO.completed("task_4", "item:completed")
        
        assert response.status == "completed"
        assert response.task_id == "task_4"
        assert response.event == "item:completed"
    
    def test_llm_error_response(self):
        """Test creating LLM error response."""
        response = WebhookResponseDTO.llm_error("task_5", "item:added")
        
        assert response.status == "llm_error"
        assert response.task_id == "task_5"
        assert response.reason == "classification_failed"
    
    def test_unsupported_event_response(self):
        """Test creating unsupported event response."""
        response = WebhookResponseDTO.unsupported_event("unknown:event")
        
        assert response.status == "unsupported"
        assert response.event == "unknown:event"
        assert response.reason == "unsupported_event"
        assert response.task_id == ""
    
    @pytest.mark.asyncio
    async def test_classification_error_flow(self):
        """Test webhook flow when classification fails with error."""
        from src.application.middleware.error_handling import ErrorHandlingMiddleware
        from src.application.middleware.base import MiddlewarePipeline
        from src.application.middleware.classification import ClassificationHandler
        from src.application.commands.classification import ClassifyTaskCommand
        
        mock_todoist_port = AsyncMock()
        mock_classifier = MagicMock()
        mock_decisions = AsyncMock()
        mock_email_service = AsyncMock()
        
        task = Task(
            todoist_id="task_456",
            content="Failed task",
            project_id="proj_1",
            labels=[]
        )
        mock_todoist_port.get_task.return_value = task
        mock_todoist_port.should_ignore_task.return_value = False
        
        mock_classifier.classify.side_effect = Exception("LLM API error")
        
        mock_todoist_port.get_task.return_value = task
        mock_todoist_port.update_task = AsyncMock()
        
        handler = ClassificationHandler(ClassifierService(llm=mock_classifier))
        pipeline = (
            MiddlewarePipeline(handler)
            .use(ErrorHandlingMiddleware(
                todoist_adapter=mock_todoist_port,
                email_service=mock_email_service,
                error_label="error"
            ))
        )
        
        service = TodoistWebhookService(
            todoist_port=mock_todoist_port,
            classifier=ClassifierService(llm=mock_classifier),
            decisions=mock_decisions,
            output_mode="labels",
            email_service=mock_email_service
        )
        service.classification_pipeline = pipeline
        
        payload = {
            "event_data": {
                "id": "task_456",
                "content": "Failed task"
            }
        }
        
        response = await service.handle("item:added", payload)
        
        assert response.status == "llm_error"
        assert response.task_id == "task_456"
        assert response.event == "item:added"
        assert response.error_detail is not None
        assert "Exception: LLM API error" in response.error_detail
        
        mock_email_service.send_error_notification.assert_called_once()
        call_args = mock_email_service.send_error_notification.call_args
        assert call_args[1]["task_id"] == "task_456"
        assert call_args[1]["task_content"] == "Failed task"
    
    def test_webhook_response_error_status(self):
        """Test that error decisions produce llm_error status."""
        decision = ClassificationDecision(
            quadrant="Q4",
            urgent=False,
            important=False,
            reason="Error occurred during classification",
            status=DecisionStatus.ERROR,
            error_detail="OpenAI API timeout"
        )
        
        response = WebhookResponseDTO.applied("task_789", "item:updated", decision)
        
        assert response.status == "llm_error"
        assert response.error_detail == "OpenAI API timeout"
        assert response.decision["quadrant"] == "Q4"
        assert response.decision["reason"] == "Error occurred during classification"
    
    def test_webhook_response_fallback_status(self):
        """Test that fallback decisions produce fallback status."""
        decision = ClassificationDecision(
            quadrant="Q4",
            urgent=False,
            important=False,
            reason="Applied default priority",
            status=DecisionStatus.FALLBACK,
            error_detail="JSON parsing failed"
        )
        
        response = WebhookResponseDTO.applied("task_890", "item:added", decision)
        
        assert response.status == "fallback"
        assert response.error_detail == "JSON parsing failed"
        assert response.decision["quadrant"] == "Q4"