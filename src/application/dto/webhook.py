from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from src.domain.models import ClassificationDecision, DecisionStatus


@dataclass(frozen=True)
class WebhookEventDTO:
    event_name: str
    task_id: str
    event_data: Dict[str, Any]
    
    @classmethod
    def from_payload(cls, event_name: str, payload: Dict[str, Any]) -> WebhookEventDTO:
        task_id = cls._extract_task_id(payload)
        return cls(
            event_name=event_name or payload.get("event_name", ""),
            task_id=task_id,
            event_data=payload
        )
    
    @staticmethod
    def _extract_task_id(payload: Dict[str, Any]) -> str:
        candidates = [
            payload.get("event_data"),
            payload.get("data"),
            payload,
        ]
        for candidate in candidates:
            if isinstance(candidate, dict) and "id" in candidate:
                return str(candidate["id"])
        raise ValueError("Todoist webhook payload did not contain a task identifier")


@dataclass(frozen=True)
class WebhookResponseDTO:
    status: Literal["applied", "ignored", "completed", "llm_error", "unsupported", "fallback"]
    task_id: str
    event: str
    reason: Optional[str] = None
    decision: Optional[Dict[str, Any]] = None
    error_detail: Optional[str] = None
    
    @classmethod
    def applied(cls, task_id: str, event: str, decision: ClassificationDecision) -> WebhookResponseDTO:
        if decision.status == DecisionStatus.ERROR:
            status = "llm_error"
        elif decision.status == DecisionStatus.FALLBACK:
            status = "fallback"
        else:
            status = "applied"
        
        return cls(
            status=status,
            task_id=task_id,
            event=event,
            decision={
                "quadrant": decision.quadrant,
                "urgent": decision.urgent,
                "important": decision.important,
                "reason": decision.reason
            },
            error_detail=decision.error_detail
        )
    
    @classmethod
    def ignored(cls, task_id: str, event: str, reason: str = "task_ignored") -> WebhookResponseDTO:
        return cls(
            status="ignored",
            task_id=task_id,
            event=event,
            reason=reason
        )
    
    @classmethod
    def completed(cls, task_id: str, event: str) -> WebhookResponseDTO:
        return cls(
            status="completed",
            task_id=task_id,
            event=event
        )
    
    @classmethod
    def llm_error(cls, task_id: str, event: str) -> WebhookResponseDTO:
        return cls(
            status="llm_error",
            task_id=task_id,
            event=event,
            reason="classification_failed"
        )
    
    @classmethod
    def unsupported_event(cls, event: str) -> WebhookResponseDTO:
        return cls(
            status="unsupported",
            task_id="",
            event=event,
            reason="unsupported_event"
        )