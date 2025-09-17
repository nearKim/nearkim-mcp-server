"""Integration tests for container wiring."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
import tempfile
import os
from pathlib import Path

from src.bootstrap.config import Config
from src.bootstrap.container import Container


class TestContainerWiring:
    """Test that the container properly wires services."""
    
    @pytest.fixture
    def test_config(self):
        """Create a test configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.data_dir = tmpdir
            config.todoist.api_key = "test_key"
            config.classification.output = "labels"
            config.ignore.project_ids = []
            config.ignore.project_names = []
            config.ignore.label_names = []
            yield config
    
    def test_container_instantiation(self, test_config):
        """Test that container can be instantiated."""
        container = Container(test_config)
        assert container is not None
        assert container.config == test_config
    
    def test_todoist_adapter_resolution(self, test_config):
        """Test that todoist_adapter can be resolved."""
        container = Container(test_config)
        adapter = container.todoist_adapter
        
        assert adapter is not None
        # Should be the simple adapter from todoist_simple.py
        from src.adapters.todoist_simple import TodoistAdapter
        assert isinstance(adapter, TodoistAdapter)
        # Should implement TodoistPort
        from src.ports.todoist import TodoistPort
        assert isinstance(adapter, TodoistPort)
    
    def test_webhook_service_resolution(self, test_config):
        """Test that webhook_service can be resolved with correct parameters."""
        container = Container(test_config)
        
        # Mock email service to avoid SMTP configuration
        with patch.object(container, 'email_service', return_value=None):
            webhook_service = container.webhook_service
            
            assert webhook_service is not None
            from src.application.service.webhook import TodoistWebhookService
            assert isinstance(webhook_service, TodoistWebhookService)
            
            # Check that dependencies were properly injected
            assert webhook_service.todoist_port is container.todoist_adapter
            assert webhook_service.output_mode == "labels"
    
    def test_todoist_service_resolution(self, test_config):
        """Test that todoist_service can be resolved with correct parameters."""
        container = Container(test_config)
        
        todoist_service = container.todoist_service
        
        assert todoist_service is not None
        from src.application.service.todoist_service import TodoistService
        assert isinstance(todoist_service, TodoistService)
        
        # Check that dependencies were properly injected
        assert todoist_service.adapter is container.todoist_adapter
        assert todoist_service.classifier is container.classifier_service
        assert todoist_service.decision_repository is container.decision_repository
        assert todoist_service.output_mode == "labels"
    
    def test_classifier_service_uses_ports(self, test_config):
        """Test that classifier service uses port interfaces."""
        container = Container(test_config)
        
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
    
    def test_decision_repository_initialization(self, test_config):
        """Test that decision repository can be initialized."""
        container = Container(test_config)
        
        repo = container.decision_repository
        
        assert repo is not None
        from src.infrastructure.persistence.decision_repository import SQLiteDecisionRepository
        assert isinstance(repo, SQLiteDecisionRepository)
        
        # Check that the database path is correct
        expected_path = Path(test_config.data_dir) / "decisions.db"
        assert repo.db_path == expected_path
    
    def test_ignore_service_configuration(self, test_config):
        """Test that ignore service is properly configured."""
        container = Container(test_config)
        
        ignore_service = container.ignore_service
        
        assert ignore_service is not None
        from src.domain.services.task_ignore import TaskIgnoreService
        assert isinstance(ignore_service, TaskIgnoreService)
        
        # Check that ignore rules are properly set
        assert ignore_service.ignore_rules.project_ids == set()
        assert ignore_service.ignore_rules.project_names == set()
        assert ignore_service.ignore_rules.label_names == set()
    
    @pytest.mark.asyncio
    async def test_container_initialization(self, test_config):
        """Test that container can be initialized without errors."""
        container = Container(test_config)
        
        # Mock services that require external connections
        container._calendar_adapter = None  # Skip Google calendar
        container._email_service = None  # Skip email service
        
        try:
            await container.initialize()
            # Should complete without errors
            assert True
        finally:
            await container.shutdown()