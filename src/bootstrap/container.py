"""Dependency injection container for the application."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from google.oauth2.credentials import Credentials

from src.adapters.google.calendar import CalendarService, GoogleCalendarAdapter
from src.adapters.todoist.adapter import TodoistAdapter
from src.application.service.todoist import TodoistService
from src.application.service.webhook import TodoistWebhookService
from src.bootstrap.config import Config
from src.domain.services.classification import ClassifierService
from src.domain.services.task_ignore import IgnoreRules, TaskIgnoreService
from src.infrastructure.cache.metadata import EntityCache
from src.infrastructure.llm.openai_adapter import OpenAIAdapter
from src.infrastructure.persistence.decision_repository import SQLiteDecisionRepository
from src.infrastructure.profile.repository import ProfileRepository

logger = logging.getLogger(__name__)


class Container:
    """Application dependency container."""
    
    def __init__(self, config: Config):
        self.config = config
        self._todoist_adapter: Optional[TodoistAdapter] = None
        self._calendar_adapter: Optional[GoogleCalendarAdapter] = None
        self._calendar_service: Optional[CalendarService] = None
        self._profile_repository: Optional[ProfileRepository] = None
        self._decision_repository: Optional[SQLiteDecisionRepository] = None
        self._classifier_service: Optional[ClassifierService] = None
        self._webhook_service: Optional[TodoistWebhookService] = None
        self._todoist_service: Optional[TodoistService] = None
        self._label_cache: Optional[EntityCache] = None
        self._project_cache: Optional[EntityCache] = None
        self._ignore_service: Optional[TaskIgnoreService] = None
        self._openai_adapter: Optional[OpenAIAdapter] = None
    
    @property
    def todoist_adapter(self) -> TodoistAdapter:
        """Get or create Todoist adapter."""
        if self._todoist_adapter is None:
            self._todoist_adapter = TodoistAdapter(
                api_key=self.config.todoist.api_key
            )
        return self._todoist_adapter
    
    @property
    def calendar_adapter(self) -> Optional[GoogleCalendarAdapter]:
        """Get or create Google Calendar adapter."""
        if self._calendar_adapter is None and self.config.google:
            credentials = self._load_google_credentials()
            if credentials:
                self._calendar_adapter = GoogleCalendarAdapter(
                    credentials=credentials,
                    calendar_ids=self.config.google.calendar_ids,
                    workday_start=self.config.google.workday_start,
                    workday_end=self.config.google.workday_end
                )
        return self._calendar_adapter
    
    @property
    def calendar_service(self) -> Optional[CalendarService]:
        """Get or create calendar service."""
        if self._calendar_service is None and self.calendar_adapter:
            self._calendar_service = CalendarService(self.calendar_adapter)
        return self._calendar_service
    
    @property
    def profile_repository(self) -> ProfileRepository:
        """Get or create profile repository."""
        if self._profile_repository is None:
            profile_path = Path(self.config.data_dir) / "profile.json"
            knowledge_path = Path(self.config.data_dir) / "knowledge.json"
            self._profile_repository = ProfileRepository(
                profile_path=profile_path,
                knowledge_path=knowledge_path
            )
        return self._profile_repository
    
    @property
    def decision_repository(self) -> SQLiteDecisionRepository:
        """Get or create decision repository."""
        if self._decision_repository is None:
            db_path = Path(self.config.data_dir) / "decisions.db"
            self._decision_repository = SQLiteDecisionRepository(db_path)
        return self._decision_repository
    
    @property
    def openai_adapter(self) -> OpenAIAdapter:
        """Get or create OpenAI adapter."""
        if self._openai_adapter is None:
            self._openai_adapter = OpenAIAdapter(
                api_key=self.config.openai.api_key,
                model=self.config.openai.model,
                temperature=self.config.openai.temperature
            )
        return self._openai_adapter
    
    @property
    def label_cache(self) -> EntityCache:
        """Get or create label cache."""
        if self._label_cache is None:
            self._label_cache = EntityCache(
                fetch_fn=self.todoist_adapter.fetch_labels
            )
        return self._label_cache
    
    @property
    def project_cache(self) -> EntityCache:
        """Get or create project cache."""
        if self._project_cache is None:
            self._project_cache = EntityCache(
                fetch_fn=self.todoist_adapter.fetch_projects
            )
        return self._project_cache
    
    @property
    def ignore_service(self) -> TaskIgnoreService:
        """Get or create ignore service."""
        if self._ignore_service is None:
            ignore_rules = IgnoreRules(
                project_ids=set(self.config.ignore.project_ids),
                project_names=set(self.config.ignore.project_names),
                label_names=set(self.config.ignore.label_names)
            )
            self._ignore_service = TaskIgnoreService(
                project_cache=self.project_cache,
                label_cache=self.label_cache,
                ignore_rules=ignore_rules
            )
        return self._ignore_service
    
    @property
    def classifier_service(self) -> ClassifierService:
        """Get or create classifier service."""
        if self._classifier_service is None:
            self._classifier_service = ClassifierService(
                llm=self.openai_adapter,
                profile_repo=self.profile_repository,
                calendar_repo=self.calendar_adapter
            )
        return self._classifier_service
    
    @property
    def webhook_service(self) -> TodoistWebhookService:
        """Get or create webhook service."""
        if self._webhook_service is None:
            self._webhook_service = TodoistWebhookService(
                classifier_service=self.classifier_service,
                ignore_service=self.ignore_service,
                todoist_adapter=self.todoist_adapter,
                decision_repository=self.decision_repository,
                webhook_secret=self.config.todoist.webhook_secret or ""
            )
        return self._webhook_service
    
    @property
    def todoist_service(self) -> TodoistService:
        """Get or create Todoist service."""
        if self._todoist_service is None:
            self._todoist_service = TodoistService(
                adapter=self.todoist_adapter,
                classifier=self.classifier_service,
                ignore_service=self.ignore_service,
                decision_repository=self.decision_repository,
                calendar_service=self.calendar_service
            )
        return self._todoist_service
    
    async def initialize(self):
        """Initialize all services."""
        logger.info("Initializing container services...")
        
        if self.calendar_adapter:
            await self.calendar_adapter.initialize()
        
        if self.calendar_service:
            await self.calendar_service.initialize()
        
        await self.profile_repository.refresh()
        
        await self.label_cache.refresh()
        await self.project_cache.refresh()
        
        logger.info("Container services initialized successfully")
    
    def _load_google_credentials(self) -> Optional[Credentials]:
        """Load Google credentials from environment or file."""
        try:
            token_path = Path(self.config.data_dir) / "google_token.json"
            if token_path.exists():
                return Credentials.from_authorized_user_file(str(token_path))
            
            if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                from google.auth import default
                credentials, _ = default()
                return credentials
            
            logger.warning("No Google credentials found")
            return None
        except Exception as e:
            logger.error(f"Failed to load Google credentials: {e}")
            return None