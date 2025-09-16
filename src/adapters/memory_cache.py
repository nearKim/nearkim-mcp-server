from __future__ import annotations

import asyncio
from typing import Dict

from src.domain.models import DecisionRecord
from src.domain.repositories import DecisionRepository


class InMemoryDecisionRepository(DecisionRepository):
    """Simple in-memory repository for classification decisions.

    The production system will likely persist decisions to durable storage, but
    the in-memory variant keeps the application services easy to unit test.
    """

    def __init__(self) -> None:
        self._records: Dict[str, DecisionRecord] = {}
        self._lock = asyncio.Lock()

    async def save(self, record: DecisionRecord) -> None:
        async with self._lock:
            self._records[record.todoist_id] = record

    async def delete(self, todoist_id: str) -> None:
        async with self._lock:
            self._records.pop(todoist_id, None)

    async def get(self, todoist_id: str) -> DecisionRecord | None:
        async with self._lock:
            return self._records.get(todoist_id)

    async def list_all(self) -> list[DecisionRecord]:
        async with self._lock:
            return list(self._records.values())
