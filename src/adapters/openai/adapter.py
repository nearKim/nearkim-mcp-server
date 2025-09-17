from __future__ import annotations

from openai import OpenAI

from pydantic import ValidationError

from src.adapters.openai.dto import ClassificationResponse, EisenhowerCommandBuilder
from src.bootstrap.settings.schemas import OpenAIConfig
from src.domain.models import ClassificationDecision
from src.domain.exceptions import LLMResponseFormatError


class OpenAIAdapter:
    def __init__(self, cfg: OpenAIConfig):
        self.client = OpenAI(
            api_key=cfg.api_key.get_secret_value() if cfg.api_key else None
        )
        self.model = cfg.model
        self.timeout = cfg.timeout_seconds

    def classify_task(
        self, task, profile, near_term, *, force_json: bool = False
    ) -> ClassificationDecision:
        request = (
            EisenhowerCommandBuilder(self.model)
            .with_task_context(task, profile, near_term, force_json=force_json)
            .build()
        )

        rsp = self.client.responses.create(
            model=request.model, input=[msg.model_dump() for msg in request.input]
        )

        try:
            response_dto = ClassificationResponse.model_validate_json(rsp.output_text)
        except ValidationError as exc:
            raise LLMResponseFormatError(
                "LLM did not return valid classification JSON"
            ) from exc

        return ClassificationDecision(
            quadrant=response_dto.quadrant,
            urgent=response_dto.urgent,
            important=response_dto.important,
            reason=response_dto.reason,
        )
