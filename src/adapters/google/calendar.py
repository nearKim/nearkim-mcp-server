"""Google Calendar adapter for timeboxing and availability management."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.domain.models import FreeSlot, FocusBlock

logger = logging.getLogger(__name__)


class GoogleCalendarAdapter:
    """Adapter for Google Calendar API operations."""
    
    def __init__(
        self,
        credentials: Credentials,
        calendar_ids: List[str],
        workday_start: int = 9,
        workday_end: int = 17
    ):
        self.credentials = credentials
        self.calendar_ids = calendar_ids or ["primary"]
        self.workday_start = workday_start
        self.workday_end = workday_end
        self.service = None
        self._sync_token: Optional[str] = None
        self._availability_cache: Dict[str, List[Dict]] = {}
        
    async def initialize(self):
        """Initialize the Google Calendar service."""
        if self.credentials.expired and self.credentials.refresh_token:
            self.credentials.refresh(Request())
        
        self.service = build('calendar', 'v3', credentials=self.credentials)
    
    async def find_free_slots(
        self,
        horizon_days: int = 7,
        min_block_minutes: int = 30
    ) -> List[FreeSlot]:
        """Find free time slots within the specified horizon."""
        now = datetime.now(timezone.utc)
        end_time = now + timedelta(days=horizon_days)
        
        # Get busy times for all calendars
        busy_times = await self._get_busy_times(now, end_time)
        
        # Calculate free slots
        free_slots = self._calculate_free_slots(
            busy_times,
            now,
            end_time,
            min_block_minutes
        )
        
        return free_slots
    
    async def _get_busy_times(
        self,
        start: datetime,
        end: datetime
    ) -> List[Dict[str, datetime]]:
        """Get busy times from all calendars."""
        try:
            # Prepare freebusy query
            body = {
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "items": [{"id": cal_id} for cal_id in self.calendar_ids]
            }
            
            # Query freebusy information
            freebusy_result = self.service.freebusy().query(body=body).execute()
            
            # Collect all busy periods
            busy_times = []
            for cal_id in self.calendar_ids:
                calendar_busy = freebusy_result['calendars'].get(cal_id, {})
                for busy_period in calendar_busy.get('busy', []):
                    busy_times.append({
                        'start': datetime.fromisoformat(busy_period['start'].replace('Z', '+00:00')),
                        'end': datetime.fromisoformat(busy_period['end'].replace('Z', '+00:00'))
                    })
            
            # Sort by start time
            busy_times.sort(key=lambda x: x['start'])
            
            return busy_times
            
        except HttpError as e:
            logger.error(f"Failed to get busy times: {e}")
            return []
    
    def _calculate_free_slots(
        self,
        busy_times: List[Dict[str, datetime]],
        start: datetime,
        end: datetime,
        min_minutes: int
    ) -> List[FreeSlot]:
        """Calculate free slots from busy times."""
        free_slots = []
        current_time = start
        
        for busy_period in busy_times:
            busy_start = busy_period['start']
            
            # Check if there's a gap before this busy period
            if current_time < busy_start:
                # Only include slots during work hours
                slot_start = self._adjust_to_workday(current_time)
                slot_end = self._adjust_to_workday_end(busy_start)
                
                if slot_start < slot_end:
                    duration = (slot_end - slot_start).total_seconds() / 60
                    if duration >= min_minutes:
                        free_slots.append(FreeSlot(
                            start=slot_start,
                            end=slot_end,
                            duration_minutes=int(duration)
                        ))
            
            # Move current time to end of busy period
            current_time = max(current_time, busy_period['end'])
        
        # Check for free time after last busy period
        if current_time < end:
            slot_start = self._adjust_to_workday(current_time)
            slot_end = self._adjust_to_workday_end(end)
            
            if slot_start < slot_end:
                duration = (slot_end - slot_start).total_seconds() / 60
                if duration >= min_minutes:
                    free_slots.append(FreeSlot(
                        start=slot_start,
                        end=slot_end,
                        duration_minutes=int(duration)
                    ))
        
        return free_slots
    
    def _adjust_to_workday(self, dt: datetime) -> datetime:
        """Adjust datetime to start of workday if needed."""
        if dt.hour < self.workday_start:
            return dt.replace(hour=self.workday_start, minute=0, second=0)
        return dt
    
    def _adjust_to_workday_end(self, dt: datetime) -> datetime:
        """Adjust datetime to end of workday if needed."""
        if dt.hour > self.workday_end:
            return dt.replace(hour=self.workday_end, minute=0, second=0)
        return dt
    
    async def create_focus_block(
        self,
        task_id: str,
        task_content: str,
        slot: FreeSlot,
        quadrant: str
    ) -> FocusBlock:
        """Create a focus block in the calendar."""
        try:
            event = {
                'summary': f"[{quadrant}] Focus: {task_content[:50]}",
                'description': f"Eisenhower task: {task_content}\nTask ID: {task_id}\nQuadrant: {quadrant}",
                'start': {
                    'dateTime': slot.start.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': slot.end.isoformat(),
                    'timeZone': 'UTC',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 10},
                    ],
                },
                'extendedProperties': {
                    'private': {
                        'todoist_task_id': task_id,
                        'eisenhower_quadrant': quadrant,
                        'created_by': 'eisenhower-mcp'
                    }
                }
            }
            
            # Create event in primary calendar
            created_event = self.service.events().insert(
                calendarId='primary',
                body=event
            ).execute()
            
            return FocusBlock(
                event_id=created_event['id'],
                task_id=task_id,
                start=slot.start,
                end=slot.end,
                calendar_id='primary'
            )
            
        except HttpError as e:
            logger.error(f"Failed to create focus block: {e}")
            raise
    
    async def cancel_focus_block(self, event_id: str, calendar_id: str = 'primary'):
        """Cancel a focus block in the calendar."""
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            logger.info(f"Cancelled focus block {event_id}")
            
        except HttpError as e:
            if e.resp.status == 404:
                logger.warning(f"Focus block {event_id} not found")
            else:
                logger.error(f"Failed to cancel focus block: {e}")
                raise
    
    async def setup_push_notifications(
        self,
        webhook_url: str,
        channel_token: str,
        ttl_hours: int = 24
    ) -> Dict[str, Any]:
        """Set up push notifications for calendar changes."""
        try:
            expiration = int((datetime.now() + timedelta(hours=ttl_hours)).timestamp() * 1000)
            
            body = {
                'id': channel_token,
                'type': 'web_hook',
                'address': webhook_url,
                'expiration': expiration,
            }
            
            watch_response = self.service.events().watch(
                calendarId='primary',
                body=body
            ).execute()
            
            logger.info(f"Set up calendar watch: {watch_response}")
            return watch_response
            
        except HttpError as e:
            logger.error(f"Failed to setup push notifications: {e}")
            raise
    
    async def sync_calendar_changes(self) -> List[Dict[str, Any]]:
        """Sync incremental calendar changes using sync token."""
        try:
            changes = []
            page_token = None
            
            while True:
                if self._sync_token:
                    # Incremental sync
                    events = self.service.events().list(
                        calendarId='primary',
                        syncToken=self._sync_token,
                        pageToken=page_token
                    ).execute()
                else:
                    # Full sync
                    events = self.service.events().list(
                        calendarId='primary',
                        pageToken=page_token
                    ).execute()
                
                changes.extend(events.get('items', []))
                
                page_token = events.get('nextPageToken')
                if not page_token:
                    # Save sync token for next incremental sync
                    self._sync_token = events.get('nextSyncToken')
                    break
            
            logger.info(f"Synced {len(changes)} calendar changes")
            return changes
            
        except HttpError as e:
            if e.resp.status == 410:
                # Sync token expired, reset and retry
                logger.warning("Sync token expired, performing full sync")
                self._sync_token = None
                return await self.sync_calendar_changes()
            else:
                logger.error(f"Failed to sync calendar changes: {e}")
                raise


class CalendarService:
    """Application service for calendar operations."""
    
    def __init__(self, adapter: GoogleCalendarAdapter):
        self.adapter = adapter
        self._focus_blocks: Dict[str, FocusBlock] = {}
    
    async def initialize(self):
        """Initialize the calendar service."""
        await self.adapter.initialize()
    
    async def find_free_slots(
        self,
        horizon_days: int = 7,
        min_block_minutes: int = 30
    ) -> List[Dict[str, Any]]:
        """Find free calendar slots."""
        slots = await self.adapter.find_free_slots(horizon_days, min_block_minutes)
        
        return [
            {
                "start": slot.start.isoformat(),
                "end": slot.end.isoformat(),
                "duration_minutes": slot.duration_minutes
            }
            for slot in slots
        ]
    
    async def schedule_q2_task(
        self,
        task_id: str,
        task_content: str,
        min_block_minutes: int = 90
    ) -> Optional[Dict[str, Any]]:
        """Schedule a Q2 task in the next available slot."""
        # Find free slots
        slots = await self.adapter.find_free_slots(
            horizon_days=7,
            min_block_minutes=min_block_minutes
        )
        
        if not slots:
            logger.warning(f"No free slots found for task {task_id}")
            return None
        
        # Use the first available slot
        chosen_slot = slots[0]
        
        # Create focus block
        focus_block = await self.adapter.create_focus_block(
            task_id=task_id,
            task_content=task_content,
            slot=chosen_slot,
            quadrant="Q2"
        )
        
        # Store focus block reference
        self._focus_blocks[task_id] = focus_block
        
        return {
            "event_id": focus_block.event_id,
            "start": focus_block.start.isoformat(),
            "end": focus_block.end.isoformat(),
            "calendar_id": focus_block.calendar_id
        }
    
    async def cancel_task_focus_blocks(self, task_id: str):
        """Cancel all focus blocks for a task."""
        if task_id in self._focus_blocks:
            focus_block = self._focus_blocks[task_id]
            await self.adapter.cancel_focus_block(
                focus_block.event_id,
                focus_block.calendar_id
            )
            del self._focus_blocks[task_id]
    
    async def handle_calendar_push(self, channel_token: str) -> List[Dict[str, Any]]:
        """Handle calendar push notification."""
        # Sync calendar changes
        changes = await self.adapter.sync_calendar_changes()
        
        # Process changes (e.g., detect conflicts with focus blocks)
        relevant_changes = []
        for event in changes:
            if event.get('status') == 'cancelled':
                # Check if this was one of our focus blocks
                extended_props = event.get('extendedProperties', {}).get('private', {})
                if extended_props.get('created_by') == 'eisenhower-mcp':
                    task_id = extended_props.get('todoist_task_id')
                    if task_id:
                        relevant_changes.append({
                            'type': 'focus_block_cancelled',
                            'task_id': task_id,
                            'event_id': event['id']
                        })
        
        return relevant_changes