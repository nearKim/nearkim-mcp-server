
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from google.oauth2.credentials import Credentials

from src.adapters.google.calendar import CalendarService, GoogleCalendarAdapter
from src.adapters.todoist_simple import TodoistAdapter
from src.application.service.todoist_service import TodoistService
from src.application.service.webhook import TodoistWebhookService
from src.bootstrap.config import Config
from src.domain.services.classification import ClassifierService
from src.domain.services.task_ignore import IgnoreRules, TaskIgnoreService
from src.infrastructure.llm.openai_adapter import OpenAIAdapter
from src.infrastructure.notifications.email_service import EmailService
from src.infrastructure.persistence.decision_repository import SQLiteDecisionRepository
from src.infrastructure.profile.repository import ProfileRepository

logger = logging.getLogger(__name__)


class Container:
    
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
        self._ignore_service: Optional[TaskIgnoreService] = None
        self._openai_adapter: Optional[OpenAIAdapter] = None
        self._email_service: Optional[EmailService] = None
    
    @property
    def todoist_adapter(self) -> TodoistAdapter:
        if self._todoist_adapter is None:
            self._todoist_adapter = TodoistAdapter(
                api_key=self.config.todoist.api_key,
                ignore_service=self.ignore_service
            )
        return self._todoist_adapter
    
    @property
    def calendar_adapter(self) -> Optional[GoogleCalendarAdapter]:
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
        if self._calendar_service is None and self.calendar_adapter:
            self._calendar_service = CalendarService(self.calendar_adapter)
        return self._calendar_service
    
    @property
    def profile_repository(self) -> ProfileRepository:
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
        if self._decision_repository is None:
            db_path = Path(self.config.data_dir) / "decisions.db"
            self._decision_repository = SQLiteDecisionRepository(db_path)
        return self._decision_repository
    
    @property
    def openai_adapter(self) -> OpenAIAdapter:
        if self._openai_adapter is None:
            self._openai_adapter = OpenAIAdapter(
                api_key=self.config.openai.api_key,
                model=self.config.openai.model,
                temperature=self.config.openai.temperature
            )
        return self._openai_adapter
    
    
    @property
    def ignore_service(self) -> TaskIgnoreService:
        if self._ignore_service is None:
            ignore_rules = IgnoreRules(
                project_ids=set(self.config.ignore.project_ids),
                project_names=set(self.config.ignore.project_names),
                label_names=set(self.config.ignore.label_names)
            )
            # TaskIgnoreService now just uses the rules directly
            self._ignore_service = TaskIgnoreService(
                ignore_rules=ignore_rules
            )
        return self._ignore_service
    
    @property
    def email_service(self) -> Optional[EmailService]:
        if self._email_service is None and self.config.email:
            self._email_service = EmailService(
                smtp_host=self.config.email.smtp_host,
                smtp_port=self.config.email.smtp_port,
                smtp_user=self.config.email.smtp_user,
                smtp_password=self.config.email.smtp_password,
                from_email=self.config.email.from_email,
                to_email=self.config.email.to_email,
                enabled=self.config.email.enabled
            )
        return self._email_service
    
    @property
    def classifier_service(self) -> ClassifierService:
        if self._classifier_service is None:
            self._classifier_service = ClassifierService(
                llm=self.openai_adapter,
                profile_port=self.profile_repository,
                schedule_port=self.calendar_adapter
            )
        return self._classifier_service
    
    @property
    def webhook_service(self) -> TodoistWebhookService:
        if self._webhook_service is None:
            self._webhook_service = TodoistWebhookService(
                todoist_port=self.todoist_adapter,
                classifier=self.classifier_service,
                decisions=self.decision_repository,
                output_mode=self.config.classification.output,
                email_service=self.email_service
            )
        return self._webhook_service
    
    @property
    def todoist_service(self) -> TodoistService:
        if self._todoist_service is None:
            self._todoist_service = TodoistService(
                adapter=self.todoist_adapter,
                classifier=self.classifier_service,
                decision_repository=self.decision_repository,
                output_mode=self.config.classification.output,
                calendar_service=self.calendar_service
            )
        return self._todoist_service
    
    async def initialize(self):
        logger.info("Initializing container services...")
        
        await self.decision_repository.connect()
        
        if self.calendar_adapter:
            await self.calendar_adapter.initialize()
        
        if self.calendar_service:
            await self.calendar_service.initialize()
        
        await self.profile_repository.refresh()
        
        logger.info("Container services initialized successfully")
    
    async def shutdown(self):
        logger.info("Shutting down container services...")
        await self.decision_repository.disconnect()
        logger.info("Container services shut down successfully")
    
    def _load_google_credentials(self) -> Optional[Credentials]:
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