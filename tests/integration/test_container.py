"""Integration tests for container wiring."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
import tempfile
import os
from pathlib import Path
from pydantic import SecretStr

from src.bootstrap.settings.settings import Settings
from src.bootstrap.settings.schemas import TodoistConfig, OpenAIConfig
from src.bootstrap.container import Container


class TestContainerWiring:
    """Test that the container properly wires services."""
    
    @pytest.fixture
    def test_settings(self):
        """Create a test settings object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = Settings(
                data_dir=Path(tmpdir),
                todoist=TodoistConfig(
                    token=SecretStr("test_key"),
                    classification=TodoistConfig.ClassificationConfig(output="labels"),
                    ignore=TodoistConfig.IgnoreRulesConfig(
                        project_ids=[],
                        projects_by_name=[],
                        labels_by_name=[]
                    )
                ),
                openai=OpenAIConfig(
                    api_key=SecretStr("test_openai_key"),
                    model="gpt-4"
                )
            )
            yield settings
    
    def test_container_instantiation(self, test_settings):
        """Test that container can be instantiated."""
        container = Container(test_settings)
        assert container is not None
        assert container.settings == test_settings
    
    def test_todoist_adapter_resolution(self, test_settings):
        """Test that todoist_adapter can be resolved."""
        container = Container(test_settings)
        adapter = container.todoist_adapter
        
        assert adapter is not None
        # Should be the simple adapter from todoist_simple.py
        from src.adapters.todoist_simple import TodoistAdapter
        assert isinstance(adapter, TodoistAdapter)
        # Should implement TodoistPort
        from src.ports.todoist import TodoistPort
        assert isinstance(adapter, TodoistPort)
    
    def test_webhook_service_resolution(self, test_settings):
        """Test that webhook_service can be resolved with correct parameters."""
        container = Container(test_settings)
        
        # Mock email service to avoid SMTP configuration
        container._email_service = None  # Set to None to skip SMTP requirements
        webhook_service = container.webhook_service
        
        assert webhook_service is not None
        from src.application.service.webhook import TodoistWebhookService
        assert isinstance(webhook_service, TodoistWebhookService)
        
        # Check that dependencies were properly injected
        assert webhook_service.todoist_port is container.todoist_adapter
        assert webhook_service.output_mode == "labels"
    
    def test_todoist_service_resolution(self, test_settings):
        """Test that todoist_service can be resolved with correct parameters."""
        container = Container(test_settings)
        
        todoist_service = container.todoist_service
        
        assert todoist_service is not None
        from src.application.service.todoist_service import TodoistService
        assert isinstance(todoist_service, TodoistService)
        
        # Check that dependencies were properly injected
        assert todoist_service.adapter is container.todoist_adapter
        assert todoist_service.classifier is container.classifier_service
        assert todoist_service.decision_repository is container.decision_repository
        assert todoist_service.output_mode == "labels"
    
    def test_classifier_service_uses_ports(self, test_settings):
        """Test that classifier service uses port interfaces."""
        container = Container(test_settings)
        
        classifier = container.classifier_service
        
        assert classifier is not None
        from src.domain.services.classification import ClassifierService
        assert isinstance(classifier, ClassifierService)
        
        # Should use port interfaces, not concrete implementations
        from src.ports.profile import ProfilePort
        from src.ports.schedule import ScheduleSummaryPort
        
        # profile_repository implements ProfilePort
        assert hasattr(classifier, 'profile_port')
        # calendar_adapter implements ScheduleSummaryPort
        assert hasattr(classifier, 'schedule_port')
    
    def test_decision_repository_initialization(self, test_settings):
        """Test that decision repository can be initialized."""
        container = Container(test_settings)
        
        repo = container.decision_repository
        
        assert repo is not None
        from src.infrastructure.persistence.decision_repository import SQLiteDecisionRepository
        assert isinstance(repo, SQLiteDecisionRepository)
        
        # Check that the database path is correct
        expected_path = Path(test_settings.data_dir) / "decisions.db"
        assert repo.db_path == expected_path
    
    def test_ignore_service_configuration(self, test_settings):
        """Test that ignore service is properly configured."""
        container = Container(test_settings)
        
        ignore_service = container.ignore_service
        
        assert ignore_service is not None
        from src.domain.services.task_ignore import TaskIgnoreService
        assert isinstance(ignore_service, TaskIgnoreService)
        
        # Check that ignore rules are properly set
        assert ignore_service.ignore_rules.project_ids == set()
        assert ignore_service.ignore_rules.project_names == set()
        assert ignore_service.ignore_rules.label_names == set()
    
    @pytest.mark.asyncio
    async def test_container_initialization(self, test_settings):
        """Test that container can be initialized without errors."""
        container = Container(test_settings)
        
        # Mock services that require external connections
        container._calendar_adapter = None  # Skip Google calendar
        container._email_service = None  # Skip email service
        
        try:
            await container.initialize()
            # Should complete without errors
            assert True
        finally:
            await container.shutdown()