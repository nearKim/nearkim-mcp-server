"""Global test fixtures and configuration."""

import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic.dataclasses import dataclass

from src.domain.entities import Task
from src.domain.models import ClassificationDecision, DecisionStatus, Quadrant


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_task():
    """Create a sample Task entity for testing."""
    return Task(
        todoist_id="123456",
        content="Review quarterly report",
        project_id="proj_123",
        labels=["work", "urgent"],
        priority=2,
        due={"date": "2024-01-15", "string": "Tomorrow"}
    )


@pytest.fixture
def sample_classification_decision():
    """Create a sample ClassificationDecision for testing."""
    return ClassificationDecision(
        quadrant="Q1",
        urgent=True,
        important=True,
        reason="Deadline tomorrow with high business impact",
        status=DecisionStatus.SUCCESS,
        error_detail=None
    )


@pytest.fixture
def sample_fallback_decision():
    """Create a sample fallback ClassificationDecision."""
    return ClassificationDecision(
        quadrant="Q4",
        urgent=False,
        important=False,
        reason="Unable to classify task. Applied default priority.",
        status=DecisionStatus.FALLBACK,
        error_detail="LLMResponseFormatError: Invalid JSON response"
    )


@pytest.fixture
def mock_llm():
    """Create a mock LLM service."""
    mock = MagicMock()
    mock.classify_task = MagicMock(return_value=ClassificationDecision(
        quadrant="Q1",
        urgent=True,
        important=True,
        reason="Test classification",
        status=DecisionStatus.SUCCESS
    ))
    return mock


@pytest.fixture
def mock_todoist_api():
    """Create a mock Todoist API."""
    mock = AsyncMock()
    mock.get_task = AsyncMock()
    mock.update_task = AsyncMock()
    mock.add_label = AsyncMock()
    mock.fetch_labels = AsyncMock(return_value=[])
    mock.fetch_projects = AsyncMock(return_value=[])
    return mock