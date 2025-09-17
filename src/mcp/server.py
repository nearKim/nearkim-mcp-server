
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from mcp import Resource, Tool, server
from mcp.types import TextContent

from src.bootstrap.container import Container
from src.domain.entities import Task

logger = logging.getLogger(__name__)


class EisenhowerMCPServer:
    
    def __init__(self, container: Container):
        self.container = container
        self.app = server.Server("eisenhower-mcp")
        self._setup_handlers()
    
    def _setup_handlers(self):
        
        @self.app.list_resources()
        async def handle_list_resources() -> List[Resource]:
            return [
                Resource(
                    uri="profile://summary",
                    name="User Profile Summary",
                    description="Compact user profile for classification context",
                    mimeType="application/json"
                ),
                Resource(
                    uri="calendar://next_7d",
                    name="Next 7 Days Calendar",
                    description="Free/busy slots for the next 7 days",
                    mimeType="application/json"
                ),
                Resource(
                    uri="eisenhower://breakdown",
                    name="Eisenhower Breakdown",
                    description="Current task distribution across quadrants",
                    mimeType="application/json"
                ),
            ]
        
        @self.app.get_resource()
        async def handle_get_resource(uri: str) -> str:
            if uri == "profile://summary":
                profile = await self.container.profile_repository.load_compact_profile()
                return json.dumps(profile, indent=2)
            
            elif uri == "calendar://next_7d":
                calendar = self.container.calendar_service
                slots = await calendar.find_free_slots(horizon_days=7, min_block_minutes=30)
                return json.dumps({"free_slots": slots}, indent=2)
            
            elif uri == "eisenhower://breakdown":
                breakdown = await self._get_quadrant_breakdown()
                return json.dumps(breakdown, indent=2)
            
            else:
                raise ValueError(f"Unknown resource URI: {uri}")
        
        @self.app.list_tools()
        async def handle_list_tools() -> List[Tool]:
            return [
                Tool(
                    name="todoist.force_reclassify",
                    description="Force reclassification of a Todoist task",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task_id": {
                                "type": "string",
                                "description": "Todoist task ID to reclassify"
                            }
                        },
                        "required": ["task_id"]
                    }
                ),
                Tool(
                    name="classification.set_output_mode",
                    description="Set classification output mode",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "mode": {
                                "type": "string",
                                "enum": ["labels", "priorities"],
                                "description": "Output mode for classification"
                            }
                        },
                        "required": ["mode"]
                    }
                ),
                Tool(
                    name="calendar.find_free_slots",
                    description="Find free calendar slots for scheduling",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "horizon_days": {
                                "type": "integer",
                                "description": "Number of days to look ahead",
                                "minimum": 1,
                                "maximum": 30
                            },
                            "min_block_minutes": {
                                "type": "integer",
                                "description": "Minimum block size in minutes",
                                "minimum": 15,
                                "maximum": 480
                            }
                        },
                        "required": ["horizon_days", "min_block_minutes"]
                    }
                ),
                Tool(
                    name="knowledge.refresh_profile",
                    description="Refresh user profile from knowledge base",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
            ]
        
        @self.app.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            try:
                if name == "todoist.force_reclassify":
                    result = await self._force_reclassify(arguments["task_id"])
                
                elif name == "classification.set_output_mode":
                    result = await self._set_output_mode(arguments["mode"])
                
                elif name == "calendar.find_free_slots":
                    result = await self._find_free_slots(
                        arguments["horizon_days"],
                        arguments["min_block_minutes"]
                    )
                
                elif name == "knowledge.refresh_profile":
                    result = await self._refresh_profile()
                
                else:
                    result = {"ok": False, "error": f"Unknown tool: {name}"}
                
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
            except Exception as e:
                logger.error(f"Tool execution failed: {name}", exc_info=e)
                error_result = {"ok": False, "error": str(e)}
                return [TextContent(type="text", text=json.dumps(error_result, indent=2))]
    
    async def _force_reclassify(self, task_id: str) -> Dict[str, Any]:
        try:
            todoist = self.container.todoist_adapter
            task_dto = await todoist.get_task(task_id)
            
            task = Task(
                todoist_id=task_dto.id,
                content=task_dto.content,
                project_id=task_dto.project_id,
                labels=task_dto.labels,
                priority=task_dto.priority,
                due=task_dto.due
            )
            
            classifier = self.container.classifier_service
            decision = await classifier.classify(task, force_json=True)
            
            await todoist.apply_eisenhower(task_id, decision)
            
            await self.container.decision_repository.save_decision(
                task_id=task_id,
                decision=decision
            )
            
            return {
                "ok": True,
                "task_id": task_id,
                "quadrant": decision.quadrant,
                "urgent": decision.urgent,
                "important": decision.important,
                "reason": decision.reason
            }
        
        except Exception as e:
            logger.error(f"Force reclassify failed for task {task_id}", exc_info=e)
            return {"ok": False, "error": str(e)}
    
    async def _set_output_mode(self, mode: str) -> Dict[str, Any]:
        if mode not in ["labels", "priorities"]:
            return {"ok": False, "error": f"Invalid mode: {mode}"}
        
        self.container.config.classification.output = mode
        
        return {
            "ok": True,
            "mode": mode,
            "message": f"Output mode set to {mode}"
        }
    
    async def _find_free_slots(
        self, horizon_days: int, min_block_minutes: int
    ) -> Dict[str, Any]:
        try:
            calendar = self.container.calendar_service
            slots = await calendar.find_free_slots(
                horizon_days=horizon_days,
                min_block_minutes=min_block_minutes
            )
            
            return {
                "ok": True,
                "horizon_days": horizon_days,
                "min_block_minutes": min_block_minutes,
                "free_slots": slots,
                "count": len(slots)
            }
        
        except Exception as e:
            logger.error("Failed to find free slots", exc_info=e)
            return {"ok": False, "error": str(e)}
    
    async def _refresh_profile(self) -> Dict[str, Any]:
        try:
            profile_repo = self.container.profile_repository
            await profile_repo.refresh()
            profile = await profile_repo.load_compact_profile()
            
            return {
                "ok": True,
                "message": "Profile refreshed successfully",
                "profile": profile
            }
        
        except Exception as e:
            logger.error("Failed to refresh profile", exc_info=e)
            return {"ok": False, "error": str(e)}
    
    async def _get_quadrant_breakdown(self) -> Dict[str, Any]:
        try:
            decisions = self.container.decision_repository
            breakdown = await decisions.get_quadrant_breakdown()
            
            return {
                "Q1": breakdown.get("Q1", 0),
                "Q2": breakdown.get("Q2", 0),
                "Q3": breakdown.get("Q3", 0),
                "Q4": breakdown.get("Q4", 0),
                "total": sum(breakdown.values()),
                "last_updated": breakdown.get("last_updated", "unknown")
            }
        
        except Exception as e:
            logger.error("Failed to get quadrant breakdown", exc_info=e)
            return {
                "Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0,
                "total": 0,
                "error": str(e)
            }
    
    async def run(self):
        async with self.app:
            await self.app.run()


def create_mcp_server(container: Container) -> EisenhowerMCPServer:
    return EisenhowerMCPServer(container)