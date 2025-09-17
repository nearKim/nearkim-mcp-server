
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.domain.models import FreeSlot, FocusBlock
from src.ports.schedule import ScheduleSummaryPort
from src.ports.calendar_scheduling import CalendarSchedulingPort

logger = logging.getLogger(__name__)


class GoogleCalendarAdapter(ScheduleSummaryPort):
    
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
        if self.credentials.expired and self.credentials.refresh_token:
            self.credentials.refresh(Request())
        
        self.service = build('calendar', 'v3', credentials=self.credentials)
    
    async def find_free_slots(
        self,
        horizon_days: int = 7,
        min_block_minutes: int = 30
    ) -> List[FreeSlot]:
        now = datetime.now(timezone.utc)
        end_time = now + timedelta(days=horizon_days)
        
        busy_times = await self._get_busy_times(now, end_time)
        
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
        try:
            body = {
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "items": [{"id": cal_id} for cal_id in self.calendar_ids]
            }
            
            freebusy_result = self.service.freebusy().query(body=body).execute()
            
            busy_times = []
            for cal_id in self.calendar_ids:
                calendar_busy = freebusy_result['calendars'].get(cal_id, {})
                for busy_period in calendar_busy.get('busy', []):
                    busy_times.append({
                        'start': datetime.fromisoformat(busy_period['start'].replace('Z', '+00:00')),
                        'end': datetime.fromisoformat(busy_period['end'].replace('Z', '+00:00'))
                    })
            
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
        free_slots = []
        current_time = start
        
        for busy_period in busy_times:
            busy_start = busy_period['start']
            
            if current_time < busy_start:
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
            
            current_time = max(current_time, busy_period['end'])
        
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
        if dt.hour < self.workday_start:
            return dt.replace(hour=self.workday_start, minute=0, second=0)
        return dt
    
    def _adjust_to_workday_end(self, dt: datetime) -> datetime:
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
        try:
            expiration = int((datetime.now() + timedelta(hours=ttl_hours)).timestamp() * 1000)
            
            body = {
                'id': channel_token,
                'type': 'web_hook',
                'address': webhook_url,
                'expiration': expiration,
            }
            
            # Run blocking Google API call in thread executor
            loop = asyncio.get_event_loop()
            watch_request = self.service.events().watch(
                calendarId='primary',
                body=body
            )
            watch_response = await loop.run_in_executor(None, watch_request.execute)
            
            logger.info(f"Set up calendar watch: {watch_response}")
            return watch_response
            
        except HttpError as e:
            logger.error(f"Failed to setup push notifications: {e}")
            raise
    
    async def next_window_summary(self, days: int = 7) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        end_time = now + timedelta(days=days)
        
        busy_times = await self._get_busy_times(now, end_time)
        
        total_busy_minutes = 0
        for busy_period in busy_times:
            duration = (busy_period['end'] - busy_period['start']).total_seconds() / 60
            total_busy_minutes += duration
        
        return {
            "days": days,
            "busy_blocks": len(busy_times),
            "total_busy_hours": round(total_busy_minutes / 60, 1),
            "average_daily_hours": round(total_busy_minutes / 60 / days, 1)
        }
    
    async def sync_calendar_changes(self) -> List[Dict[str, Any]]:
        try:
            changes = []
            page_token = None
            
            while True:
                if self._sync_token:
                    events = self.service.events().list(
                        calendarId='primary',
                        syncToken=self._sync_token,
                        pageToken=page_token
                    ).execute()
                else:
                    events = self.service.events().list(
                        calendarId='primary',
                        pageToken=page_token
                    ).execute()
                
                changes.extend(events.get('items', []))
                
                page_token = events.get('nextPageToken')
                if not page_token:
                    self._sync_token = events.get('nextSyncToken')
                    break
            
            logger.info(f"Synced {len(changes)} calendar changes")
            return changes
            
        except HttpError as e:
            if e.resp.status == 410:
                logger.warning("Sync token expired, performing full sync")
                self._sync_token = None
                return await self.sync_calendar_changes()
            else:
                logger.error(f"Failed to sync calendar changes: {e}")
                raise


class CalendarService(CalendarSchedulingPort):
    
    def __init__(self, adapter: GoogleCalendarAdapter):
        self.adapter = adapter
        self._focus_blocks: Dict[str, FocusBlock] = {}
    
    async def initialize(self):
        await self.adapter.initialize()
    
    async def find_free_slots(
        self,
        horizon_days: int = 7,
        min_block_minutes: int = 30
    ) -> List[Dict[str, Any]]:
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
        slots = await self.adapter.find_free_slots(
            horizon_days=7,
            min_block_minutes=min_block_minutes
        )
        
        if not slots:
            logger.warning(f"No free slots found for task {task_id}")
            return None
        
        chosen_slot = slots[0]
        
        focus_block = await self.adapter.create_focus_block(
            task_id=task_id,
            task_content=task_content,
            slot=chosen_slot,
            quadrant="Q2"
        )
        
        self._focus_blocks[task_id] = focus_block
        
        return {
            "event_id": focus_block.event_id,
            "start": focus_block.start.isoformat(),
            "end": focus_block.end.isoformat(),
            "calendar_id": focus_block.calendar_id
        }
    
    async def cancel_task_focus_blocks(self, task_id: str):
        if task_id in self._focus_blocks:
            focus_block = self._focus_blocks[task_id]
            await self.adapter.cancel_focus_block(
                focus_block.event_id,
                focus_block.calendar_id
            )
            del self._focus_blocks[task_id]
    
    async def cancel_scheduled_task(self, event_id: str) -> bool:
        """
        Cancel a previously scheduled task.
        
        Args:
            event_id: The calendar event ID to cancel
            
        Returns:
            True if canceled successfully, False otherwise
        """
        try:
            # Find the task_id associated with this event
            task_id = None
            for tid, block in self._focus_blocks.items():
                if block.event_id == event_id:
                    task_id = tid
                    break
            
            if task_id:
                await self.cancel_task_focus_blocks(task_id)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to cancel scheduled task {event_id}: {e}")
            return False
    
    async def handle_calendar_push(self, channel_token: str) -> List[Dict[str, Any]]:
        changes = await self.adapter.sync_calendar_changes()
        
        relevant_changes = []
        for event in changes:
            if event.get('status') == 'cancelled':
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