from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from databases import Database

from src.domain.models import (
    ClassificationDecision,
    DecisionRecord,
    DecisionStatus,
    Quadrant,
)
from src.domain.repositories import DecisionRepository

logger = logging.getLogger(__name__)


class SQLiteDecisionRepository(DecisionRepository):
    
    def __init__(self, db_path: Path):
        self.db_url = f"sqlite:///{db_path}"
        self.database: Optional[Database] = None
        self.db_path = db_path
    
    async def connect(self):
        self.database = Database(self.db_url)
        await self.database.connect()
        await self._ensure_schema()
    
    async def disconnect(self):
        if self.database:
            await self.database.disconnect()
    
    async def _ensure_schema(self):
        create_table_query = """
            CREATE TABLE IF NOT EXISTS decisions (
                todoist_id TEXT PRIMARY KEY,
                quadrant TEXT NOT NULL,
                urgent BOOLEAN NOT NULL,
                important BOOLEAN NOT NULL,
                reason TEXT NOT NULL,
                applied_mode TEXT NOT NULL,
                status TEXT NOT NULL,
                error_detail TEXT,
                updated_at TEXT NOT NULL
            )
        """
        
        create_index_quadrant = """
            CREATE INDEX IF NOT EXISTS idx_decisions_quadrant 
            ON decisions(quadrant)
        """
        
        create_index_updated = """
            CREATE INDEX IF NOT EXISTS idx_decisions_updated 
            ON decisions(updated_at)
        """
        
        await self.database.execute(create_table_query)
        await self.database.execute(create_index_quadrant)
        await self.database.execute(create_index_updated)
    
    async def save(self, record: DecisionRecord) -> None:
        query = """
            INSERT OR REPLACE INTO decisions (
                todoist_id, quadrant, urgent, important, reason,
                applied_mode, status, error_detail, updated_at
            ) VALUES (:todoist_id, :quadrant, :urgent, :important, :reason,
                     :applied_mode, :status, :error_detail, :updated_at)
        """
        
        values = {
            "todoist_id": record.todoist_id,
            "quadrant": record.quadrant,
            "urgent": record.urgent,
            "important": record.important,
            "reason": record.reason,
            "applied_mode": record.applied_mode,
            "status": record.status.value,
            "error_detail": record.error_detail,
            "updated_at": record.updated_at.isoformat()
        }
        
        await self.database.execute(query=query, values=values)
        logger.debug(f"Saved decision for task {record.todoist_id}")
    
    async def save_decision(self, task_id: str, decision: ClassificationDecision) -> None:
        record = DecisionRecord.from_decision(
            todoist_id=task_id,
            decision=decision,
            applied_mode="labels"
        )
        await self.save(record)
    
    async def get(self, todoist_id: str) -> Optional[DecisionRecord]:
        query = "SELECT * FROM decisions WHERE todoist_id = :todoist_id"
        row = await self.database.fetch_one(query=query, values={"todoist_id": todoist_id})
        
        if row:
            return self._row_to_record(dict(row))
        return None
    
    async def delete(self, todoist_id: str) -> None:
        query = "DELETE FROM decisions WHERE todoist_id = :todoist_id"
        await self.database.execute(query=query, values={"todoist_id": todoist_id})
        logger.debug(f"Deleted decision for task {todoist_id}")
    
    async def get_quadrant_breakdown(self) -> Dict[str, Any]:
        query = """
            SELECT quadrant, COUNT(*) as count 
            FROM decisions 
            WHERE status != 'error'
            GROUP BY quadrant
        """
        rows = await self.database.fetch_all(query=query)
        
        breakdown = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
        for row in rows:
            breakdown[row["quadrant"]] = row["count"]
        
        last_updated_query = "SELECT MAX(updated_at) as last_updated FROM decisions"
        result = await self.database.fetch_one(query=last_updated_query)
        last_updated = result["last_updated"] if result else None
        
        breakdown["last_updated"] = last_updated or "unknown"
        
        return breakdown
    
    async def get_recent_decisions(self, limit: int = 10) -> List[DecisionRecord]:
        query = """
            SELECT * FROM decisions 
            ORDER BY updated_at DESC 
            LIMIT :limit
        """
        rows = await self.database.fetch_all(query=query, values={"limit": limit})
        return [self._row_to_record(dict(row)) for row in rows]
    
    async def get_by_quadrant(self, quadrant: Quadrant) -> List[DecisionRecord]:
        query = """
            SELECT * FROM decisions 
            WHERE quadrant = :quadrant AND status != 'error'
            ORDER BY updated_at DESC
        """
        rows = await self.database.fetch_all(query=query, values={"quadrant": quadrant})
        return [self._row_to_record(dict(row)) for row in rows]
    
    def _row_to_record(self, row: Dict[str, Any]) -> DecisionRecord:
        return DecisionRecord(
            todoist_id=row["todoist_id"],
            quadrant=row["quadrant"],
            urgent=bool(row["urgent"]),
            important=bool(row["important"]),
            reason=row["reason"],
            applied_mode=row["applied_mode"],
            status=DecisionStatus(row["status"]),
            error_detail=row["error_detail"],
            updated_at=datetime.fromisoformat(row["updated_at"])
        )