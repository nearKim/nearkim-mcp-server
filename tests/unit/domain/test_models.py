"""Tests for domain models."""

import pytest
from datetime import datetime, timezone

from src.domain.models import (
    ClassificationDecision,
    DecisionRecord,
    DecisionStatus,
    Quadrant,
)


class TestClassificationDecision:
    """Test ClassificationDecision model."""
    
    def test_create_success_decision(self):
        """Test creating a successful classification decision."""
        decision = ClassificationDecision(
            quadrant="Q1",
            urgent=True,
            important=True,
            reason="High priority task",
            status=DecisionStatus.SUCCESS,
            error_detail=None
        )
        
        assert decision.quadrant == "Q1"
        assert decision.urgent is True
        assert decision.important is True
        assert decision.reason == "High priority task"
        assert decision.status == DecisionStatus.SUCCESS
        assert decision.error_detail is None
        assert decision.is_fallback is False
    
    def test_create_fallback_decision(self):
        """Test creating a fallback classification decision."""
        decision = ClassificationDecision(
            quadrant="Q4",
            urgent=False,
            important=False,
            reason="Fallback applied",
            status=DecisionStatus.FALLBACK,
            error_detail="Error occurred"
        )
        
        assert decision.quadrant == "Q4"
        assert decision.status == DecisionStatus.FALLBACK
        assert decision.error_detail == "Error occurred"
        assert decision.is_fallback is True
    
    def test_create_fallback_from_exception(self):
        """Test create_fallback class method."""
        error = ValueError("Test error message")
        decision = ClassificationDecision.create_fallback(
            error=error,
            default_quadrant="Q3"
        )
        
        assert decision.quadrant == "Q3"
        assert decision.urgent is False
        assert decision.important is False
        assert decision.status == DecisionStatus.FALLBACK
        assert "ValueError: Test error message" in decision.error_detail
        assert decision.is_fallback is True
    
    def test_default_status_is_success(self):
        """Test that default status is SUCCESS."""
        decision = ClassificationDecision(
            quadrant="Q2",
            urgent=False,
            important=True,
            reason="Important but not urgent"
        )
        
        assert decision.status == DecisionStatus.SUCCESS
        assert decision.error_detail is None
    
    def test_all_quadrants(self):
        """Test all valid quadrant values."""
        quadrants: list[Quadrant] = ["Q1", "Q2", "Q3", "Q4"]
        for q in quadrants:
            decision = ClassificationDecision(
                quadrant=q,
                urgent=q in ["Q1", "Q3"],
                important=q in ["Q1", "Q2"],
                reason=f"Task in {q}"
            )
            assert decision.quadrant == q


class TestDecisionRecord:
    """Test DecisionRecord model."""
    
    def test_create_decision_record(self):
        """Test creating a DecisionRecord."""
        now = datetime.now(timezone.utc)
        record = DecisionRecord(
            quadrant="Q1",
            urgent=True,
            important=True,
            reason="Test reason",
            todoist_id="task_123",
            applied_mode="labels",
            updated_at=now,
            status=DecisionStatus.SUCCESS,
            error_detail=None
        )
        
        assert record.todoist_id == "task_123"
        assert record.applied_mode == "labels"
        assert record.updated_at == now
        assert record.quadrant == "Q1"
    
    def test_from_decision_factory_method(self):
        """Test from_decision factory method."""
        decision = ClassificationDecision(
            quadrant="Q2",
            urgent=False,
            important=True,
            reason="Important task",
            status=DecisionStatus.SUCCESS,
            error_detail=None
        )
        
        record = DecisionRecord.from_decision(
            todoist_id="task_456",
            decision=decision,
            applied_mode="priorities"
        )
        
        assert record.todoist_id == "task_456"
        assert record.quadrant == "Q2"
        assert record.urgent is False
        assert record.important is True
        assert record.reason == "Important task"
        assert record.applied_mode == "priorities"
        assert record.status == DecisionStatus.SUCCESS
        assert record.error_detail is None
        assert isinstance(record.updated_at, datetime)
    
    def test_from_decision_with_custom_timestamp(self):
        """Test from_decision with custom timestamp."""
        decision = ClassificationDecision(
            quadrant="Q3",
            urgent=True,
            important=False,
            reason="Urgent task"
        )
        
        custom_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        record = DecisionRecord.from_decision(
            todoist_id="task_789",
            decision=decision,
            applied_mode="labels",
            updated_at=custom_time
        )
        
        assert record.updated_at == custom_time
    
    def test_from_decision_with_fallback(self):
        """Test from_decision with a fallback decision."""
        error = RuntimeError("API error")
        decision = ClassificationDecision.create_fallback(error)
        
        record = DecisionRecord.from_decision(
            todoist_id="task_999",
            decision=decision,
            applied_mode="labels"
        )
        
        assert record.status == DecisionStatus.FALLBACK
        assert record.error_detail is not None
        assert "RuntimeError" in record.error_detail
        assert record.quadrant == "Q4"  # Default fallback quadrant


class TestDecisionStatus:
    """Test DecisionStatus enum."""
    
    def test_status_values(self):
        """Test all DecisionStatus values."""
        assert DecisionStatus.SUCCESS.value == "success"
        assert DecisionStatus.FALLBACK.value == "fallback"
        assert DecisionStatus.ERROR.value == "error"
    
    def test_status_comparison(self):
        """Test DecisionStatus comparison."""
        status1 = DecisionStatus.SUCCESS
        status2 = DecisionStatus.SUCCESS
        status3 = DecisionStatus.FALLBACK
        
        assert status1 == status2
        assert status1 != status3