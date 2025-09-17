"""Profile repository implementation for user context management."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ProfileRepository:
    """Repository for managing user profile and knowledge base."""
    
    def __init__(self, profile_path: Path, knowledge_path: Path):
        self.profile_path = profile_path
        self.knowledge_path = knowledge_path
        self._profile_cache: Optional[Dict[str, Any]] = None
        self._knowledge_cache: Optional[Dict[str, Any]] = None
    
    async def load_compact_profile(self) -> Dict[str, Any]:
        """Load compact user profile for classification context."""
        if self._profile_cache is None:
            await self.refresh()
        
        profile = self._profile_cache or {}
        
        return {
            "name": profile.get("name", "Unknown"),
            "role": profile.get("role", ""),
            "goals": profile.get("goals", []),
            "priorities": profile.get("priorities", []),
            "work_hours": profile.get("work_hours", {"start": 9, "end": 17}),
            "timezone": profile.get("timezone", "UTC")
        }
    
    async def load_full_profile(self) -> Dict[str, Any]:
        """Load full user profile."""
        if self._profile_cache is None:
            await self.refresh()
        
        return self._profile_cache or {}
    
    async def load_knowledge(self) -> Dict[str, Any]:
        """Load knowledge base."""
        if self._knowledge_cache is None:
            await self.refresh()
        
        return self._knowledge_cache or {}
    
    async def refresh(self):
        """Refresh profile and knowledge from disk."""
        try:
            if self.profile_path.exists():
                with self.profile_path.open() as f:
                    self._profile_cache = json.load(f)
                logger.info(f"Loaded profile from {self.profile_path}")
            else:
                logger.warning(f"Profile file not found: {self.profile_path}")
                self._profile_cache = self._get_default_profile()
        except Exception as e:
            logger.error(f"Failed to load profile: {e}")
            self._profile_cache = self._get_default_profile()
        
        try:
            if self.knowledge_path.exists():
                with self.knowledge_path.open() as f:
                    self._knowledge_cache = json.load(f)
                logger.info(f"Loaded knowledge from {self.knowledge_path}")
            else:
                logger.warning(f"Knowledge file not found: {self.knowledge_path}")
                self._knowledge_cache = {}
        except Exception as e:
            logger.error(f"Failed to load knowledge: {e}")
            self._knowledge_cache = {}
    
    async def save_profile(self, profile: Dict[str, Any]):
        """Save profile to disk."""
        try:
            self.profile_path.parent.mkdir(parents=True, exist_ok=True)
            with self.profile_path.open('w') as f:
                json.dump(profile, f, indent=2)
            self._profile_cache = profile
            logger.info(f"Saved profile to {self.profile_path}")
        except Exception as e:
            logger.error(f"Failed to save profile: {e}")
            raise
    
    async def save_knowledge(self, knowledge: Dict[str, Any]):
        """Save knowledge base to disk."""
        try:
            self.knowledge_path.parent.mkdir(parents=True, exist_ok=True)
            with self.knowledge_path.open('w') as f:
                json.dump(knowledge, f, indent=2)
            self._knowledge_cache = knowledge
            logger.info(f"Saved knowledge to {self.knowledge_path}")
        except Exception as e:
            logger.error(f"Failed to save knowledge: {e}")
            raise
    
    def _get_default_profile(self) -> Dict[str, Any]:
        """Get default profile structure."""
        return {
            "name": "User",
            "role": "",
            "goals": [],
            "priorities": [],
            "work_hours": {"start": 9, "end": 17},
            "timezone": "UTC",
            "preferences": {
                "default_quadrant": "Q4",
                "auto_schedule_q2": False,
                "min_focus_block_minutes": 90
            }
        }