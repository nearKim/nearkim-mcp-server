
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class TodoistConfig:
    api_key: str
    webhook_secret: Optional[str] = None


@dataclass
class OpenAIConfig:
    api_key: str
    model: str = "gpt-4"
    temperature: float = 0.3


@dataclass
class GoogleConfig:
    calendar_ids: List[str] = field(default_factory=lambda: ["primary"])
    workday_start: int = 9
    workday_end: int = 17


@dataclass
class ClassificationConfig:
    output: str = "labels"  # "labels" or "priorities"
    default_quadrant: str = "Q4"
    force_json: bool = True


@dataclass
class IgnoreConfig:
    project_ids: List[str] = field(default_factory=list)
    project_names: List[str] = field(default_factory=list)
    label_names: List[str] = field(default_factory=lambda: ["no-eisenhower"])


@dataclass
class EmailConfig:
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    from_email: str
    to_email: str
    enabled: bool = True


@dataclass
class Config:
    todoist: TodoistConfig
    openai: OpenAIConfig
    google: Optional[GoogleConfig] = None
    email: Optional[EmailConfig] = None
    classification: ClassificationConfig = field(default_factory=ClassificationConfig)
    ignore: IgnoreConfig = field(default_factory=IgnoreConfig)
    data_dir: str = "./data"
    log_level: str = "INFO"
    
    @classmethod
    def from_yaml(cls, path: Path) -> Config:
        with path.open() as f:
            data = yaml.safe_load(f)
        
        return cls(
            todoist=TodoistConfig(
                api_key=data["todoist"]["api_key"],
                webhook_secret=data["todoist"].get("webhook_secret")
            ),
            openai=OpenAIConfig(
                api_key=data["openai"]["api_key"],
                model=data["openai"].get("model", "gpt-4"),
                temperature=data["openai"].get("temperature", 0.3)
            ),
            google=GoogleConfig(
                calendar_ids=data["google"].get("calendar_ids", ["primary"]),
                workday_start=data["google"].get("workday_start", 9),
                workday_end=data["google"].get("workday_end", 17)
            ) if "google" in data else None,
            classification=ClassificationConfig(
                output=data.get("classification", {}).get("output", "labels"),
                default_quadrant=data.get("classification", {}).get("default_quadrant", "Q4"),
                force_json=data.get("classification", {}).get("force_json", True)
            ),
            ignore=IgnoreConfig(
                project_ids=data.get("ignore", {}).get("project_ids", []),
                project_names=data.get("ignore", {}).get("project_names", []),
                label_names=data.get("ignore", {}).get("label_names", ["no-eisenhower"])
            ),
            email=EmailConfig(
                smtp_host=data["email"]["smtp_host"],
                smtp_port=data["email"]["smtp_port"],
                smtp_user=data["email"]["smtp_user"],
                smtp_password=data["email"]["smtp_password"],
                from_email=data["email"]["from_email"],
                to_email=data["email"]["to_email"],
                enabled=data["email"].get("enabled", True)
            ) if "email" in data else None,
            data_dir=data.get("data_dir", "./data"),
            log_level=data.get("log_level", "INFO")
        )
    
    @classmethod
    def from_env(cls) -> Config:
        return cls(
            todoist=TodoistConfig(
                api_key=os.environ["TODOIST_API_KEY"],
                webhook_secret=os.getenv("TODOIST_WEBHOOK_SECRET")
            ),
            openai=OpenAIConfig(
                api_key=os.environ["OPENAI_API_KEY"],
                model=os.getenv("OPENAI_MODEL", "gpt-4"),
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.3"))
            ),
            google=GoogleConfig(
                calendar_ids=os.getenv("GOOGLE_CALENDAR_IDS", "primary").split(","),
                workday_start=int(os.getenv("WORKDAY_START", "9")),
                workday_end=int(os.getenv("WORKDAY_END", "17"))
            ) if os.getenv("GOOGLE_CALENDAR_IDS") else None,
            classification=ClassificationConfig(
                output=os.getenv("CLASSIFICATION_OUTPUT", "labels"),
                default_quadrant=os.getenv("DEFAULT_QUADRANT", "Q4"),
                force_json=os.getenv("FORCE_JSON", "true").lower() == "true"
            ),
            ignore=IgnoreConfig(
                project_ids=os.getenv("IGNORE_PROJECT_IDS", "").split(",") if os.getenv("IGNORE_PROJECT_IDS") else [],
                project_names=os.getenv("IGNORE_PROJECT_NAMES", "").split(",") if os.getenv("IGNORE_PROJECT_NAMES") else [],
                label_names=os.getenv("IGNORE_LABEL_NAMES", "no-eisenhower").split(",")
            ),
            email=EmailConfig(
                smtp_host=os.environ["SMTP_HOST"],
                smtp_port=int(os.environ["SMTP_PORT"]),
                smtp_user=os.environ["SMTP_USER"],
                smtp_password=os.environ["SMTP_PASSWORD"],
                from_email=os.environ["FROM_EMAIL"],
                to_email=os.environ["TO_EMAIL"],
                enabled=os.getenv("EMAIL_ENABLED", "true").lower() == "true"
            ) if os.getenv("SMTP_HOST") else None,
            data_dir=os.getenv("DATA_DIR", "./data"),
            log_level=os.getenv("LOG_LEVEL", "INFO")
        )