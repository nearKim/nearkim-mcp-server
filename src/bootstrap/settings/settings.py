from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .schemas import (
    AppConfig,
    GoogleCalendarConfig,
    OpenAIConfig,
    SchedulingConfig,
    TodoistConfig,
)


class EmailConfig:
    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_email: Optional[str] = None,
        to_email: Optional[str] = None,
        enabled: bool = True
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.to_email = to_email
        self.enabled = enabled and all([
            smtp_host, smtp_port, smtp_user, smtp_password, from_email, to_email
        ])


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore"
    )

    app: AppConfig = Field(default_factory=AppConfig)
    todoist: TodoistConfig = Field(default_factory=TodoistConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    google_calendar: GoogleCalendarConfig = Field(default_factory=GoogleCalendarConfig)
    scheduling: SchedulingConfig = Field(default_factory=SchedulingConfig)
    data_dir: Path = Path("./data")
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    
    @property
    def email(self) -> Optional[EmailConfig]:
        if all([
            os.getenv("EMAIL_SMTP_HOST"),
            os.getenv("EMAIL_SMTP_PORT"),
            os.getenv("EMAIL_SMTP_USER"),
            os.getenv("EMAIL_SMTP_PASSWORD"),
            os.getenv("EMAIL_FROM"),
            os.getenv("EMAIL_TO")
        ]):
            return EmailConfig(
                smtp_host=os.environ["EMAIL_SMTP_HOST"],
                smtp_port=int(os.environ["EMAIL_SMTP_PORT"]),
                smtp_user=os.environ["EMAIL_SMTP_USER"],
                smtp_password=os.environ["EMAIL_SMTP_PASSWORD"],
                from_email=os.environ["EMAIL_FROM"],
                to_email=os.environ["EMAIL_TO"],
                enabled=os.getenv("EMAIL_ENABLED", "true").lower() == "true"
            )
        return None
    
    def get_db_url(self) -> str:
        db_path = self.data_dir / "decisions.db"
        return f"sqlite+aiosqlite:///{db_path}"
    
    @classmethod
    def from_env(cls) -> Settings:
        settings = cls()
        if "TODOIST_API_KEY" in os.environ:
            settings.todoist.token = SecretStr(os.environ["TODOIST_API_KEY"])
        if "TODOIST_WEBHOOK_SECRET" in os.environ:
            settings.todoist.webhook_secret = SecretStr(os.environ["TODOIST_WEBHOOK_SECRET"])
        if "OPENAI_API_KEY" in os.environ:
            settings.openai.api_key = SecretStr(os.environ["OPENAI_API_KEY"])
        if "OPENAI_MODEL" in os.environ:
            settings.openai.model = os.environ["OPENAI_MODEL"]
        
        return settings

