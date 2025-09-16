from __future__ import annotations

from openai import OpenAI

from src.adapters.openai.dto import ClassificationResponse, EisenhowerCommandBuilder
from src.bootstrap.settings.schemas import OpenAIConfig
from src.domain.models import ClassificationDecision


class OpenAIAdapter:
    def __init__(self, cfg: OpenAIConfig):
        self.client = OpenAI(
            api_key=cfg.api_key.get_secret_value() if cfg.api_key else None
        )
        self.model = cfg.model
        self.timeout = cfg.timeout_seconds

    def classify_task(self, task, profile, near_term) -> ClassificationDecision:
        request = (
            EisenhowerCommandBuilder(self.model)
            .with_task_context(task, profile, near_term)
            .build()
        )

        rsp = self.client.responses.create(
            model=request.model, input=[msg.model_dump() for msg in request.input]
        )

        response_dto = ClassificationResponse.model_validate_json(rsp.output_text)

        return ClassificationDecision(
            quadrant=response_dto.quadrant,
            urgent=response_dto.urgent,
            important=response_dto.important,
            reason=response_dto.reason,
        )
