from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from .schemas import AppConfig, TodoistConfig, OpenAIConfig, GoogleCalendarConfig, SchedulingConfig

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # group sub-configs; each field pulls from ENV via nested prefixes if you wish
    app: AppConfig = AppConfig()
    todoist: TodoistConfig = TodoistConfig()
    openai: OpenAIConfig = OpenAIConfig()
    gcal: GoogleCalendarConfig = GoogleCalendarConfig()
    scheduling: SchedulingConfig = SchedulingConfig()

    # Example: to support CSV for calendar IDs, add a validator if needed.
