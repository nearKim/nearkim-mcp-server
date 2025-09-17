from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field, SecretStr


class TodoistConfig(BaseModel):
    class ClassificationConfig(BaseModel):
        output: Literal["labels", "priorities"] = "labels"
        label_urgent: str = "@urgent"
        label_important: str = "@important"
        autocreate_labels: bool = Field(True, alias="auto_create_labels")

    class IgnoreRulesConfig(BaseModel):
        project_ids: List[str] = []
        projects_by_name: List[str] = ["Shopping"]
        labels_by_name: List[str] = ["no-classify"]

    token: SecretStr | None = None
    client_id: str | None = None
    client_secret: SecretStr | None = None
    redirect_uri: str | None = None
    webhook_secret: SecretStr | None = None
    classification: ClassificationConfig = ClassificationConfig()
    ignore: IgnoreRulesConfig = IgnoreRulesConfig()


class OpenAIConfig(BaseModel):
    api_key: SecretStr | None = None
    model: str = "gpt-5"
    timeout_seconds: int = 30


class GoogleCalendarConfig(BaseModel):
    credentials_json_path: str | None = None
    calendar_ids: List[str] = ["primary"]
    channel_token: str | None = None
    watch_ttl_hours: int = 168


class SchedulingConfig(BaseModel):
    min_focus_minutes: int = 90
    workday_start_hour: int = 9
    workday_end_hour: int = 19


class AppConfig(BaseModel):
    env: Literal["local", "dev", "prod"] = "local"
    timezone: str = "America/New_York"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
