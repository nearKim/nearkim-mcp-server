from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from .schemas import (
    AppConfig,
    GoogleCalendarConfig,
    OpenAIConfig,
    SchedulingConfig,
    TodoistConfig,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    app: AppConfig = AppConfig()
    todoist: TodoistConfig = TodoistConfig()
    openai: OpenAIConfig = OpenAIConfig()
    gcal: GoogleCalendarConfig = GoogleCalendarConfig()
    scheduling: SchedulingConfig = SchedulingConfig()

