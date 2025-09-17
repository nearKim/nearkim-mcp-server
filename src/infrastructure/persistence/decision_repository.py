"""Decision repository implementation for storing classification records."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.domain.models import (
    ClassificationDecision,
    DecisionRecord,
    DecisionStatus,
    Quadrant,
)
from src.domain.repositories import DecisionRepository

logger = logging.getLogger(__name__)


class SQLiteDecisionRepository(DecisionRepository):
    """SQLite-based decision repository implementation."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_schema()
    
    def _ensure_schema(self):
        """Ensure database schema exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
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
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_decisions_quadrant 
                ON decisions(quadrant)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_decisions_updated 
                ON decisions(updated_at)
            """)
    
    async def save(self, record: DecisionRecord) -> None:
        """Save a decision record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO decisions (
                    todoist_id, quadrant, urgent, important, reason,
                    applied_mode, status, error_detail, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.todoist_id,
                record.quadrant,
                record.urgent,
                record.important,
                record.reason,
                record.applied_mode,
                record.status.value,
                record.error_detail,
                record.updated_at.isoformat()
            ))
        
        logger.debug(f"Saved decision for task {record.todoist_id}")
    
    async def save_decision(self, task_id: str, decision: ClassificationDecision) -> None:
        """Save a classification decision (backward compatibility)."""
        record = DecisionRecord.from_decision(
            todoist_id=task_id,
            decision=decision,
            applied_mode="labels"
        )
        await self.save(record)
    
    async def get(self, todoist_id: str) -> Optional[DecisionRecord]:
        """Get a decision record by task ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM decisions WHERE todoist_id = ?",
                (todoist_id,)
            )
            row = cursor.fetchone()
        
        if row:
            return self._row_to_record(row)
        return None
    
    async def delete(self, todoist_id: str) -> None:
        """Delete a decision record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM decisions WHERE todoist_id = ?",
                (todoist_id,)
            )
        
        logger.debug(f"Deleted decision for task {todoist_id}")
    
    async def get_quadrant_breakdown(self) -> Dict[str, Any]:
        """Get task count breakdown by quadrant."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT quadrant, COUNT(*) as count 
                FROM decisions 
                WHERE status != 'error'
                GROUP BY quadrant
            """)
            rows = cursor.fetchall()
        
        breakdown = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
        for quadrant, count in rows:
            breakdown[quadrant] = count
        
        cursor = conn.execute("""
            SELECT MAX(updated_at) as last_updated 
            FROM decisions
        """)
        last_updated = cursor.fetchone()[0]
        
        breakdown["last_updated"] = last_updated or "unknown"
        
        return breakdown
    
    async def get_recent_decisions(self, limit: int = 10) -> List[DecisionRecord]:
        """Get recent decision records."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM decisions 
                ORDER BY updated_at DESC 
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
        
        return [self._row_to_record(row) for row in rows]
    
    async def get_by_quadrant(self, quadrant: Quadrant) -> List[DecisionRecord]:
        """Get all decisions for a specific quadrant."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM decisions 
                WHERE quadrant = ? AND status != 'error'
                ORDER BY updated_at DESC
            """, (quadrant,))
            rows = cursor.fetchall()
        
        return [self._row_to_record(row) for row in rows]
    
    def _row_to_record(self, row: sqlite3.Row) -> DecisionRecord:
        """Convert database row to DecisionRecord."""
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