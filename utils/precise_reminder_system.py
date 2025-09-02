import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
import discord
from discord.ext import tasks
from utils.smart_time_formatter import SmartTimeFormatter

logger = logging.getLogger(__name__)

@dataclass
class ReminderEvent:
    """Represents a reminder event with precise timing"""
    event_id: int
    guild_id: int
    event_name: str
    event_date: datetime
    reminder_time: datetime
    reminder_hours_before: int
    created_by_id: Optional[int] = None
    notification_sent: bool = False

class PreciseReminderSystem:
    """
    High-precision reminder system that checks every second for exact timing.
    Handles event reminders with pinpoint accuracy.
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.active_reminders: Dict[int, ReminderEvent] = {}
        self.reminder_callbacks: Dict[str, Callable] = {}
        self.is_running = False
        self._lock = asyncio.Lock()
        
    async def start(self):
        """Start the precise reminder system"""
        if not self.is_running:
            self.is_running = True
            self.precise_reminder_loop.start()
            logger.info("Precise reminder system started with 1-second intervals")
    
    async def stop(self):
        """Stop the precise reminder system"""
        if self.is_running:
            self.is_running = False
            self.precise_reminder_loop.cancel()
            logger.info("Precise reminder system stopped")
    
    @tasks.loop(seconds=1.0)
    async def precise_reminder_loop(self):
        """Main loop that checks for reminders every second"""
        try:
            current_time = datetime.now()
            reminders_to_send = []
            
            async with self._lock:
                # Check all active reminders
                for event_id, reminder in list(self.active_reminders.items()):
                    if reminder.notification_sent:
                        continue
                    
                    # Check if it's time to send the reminder (within 1 second accuracy)
                    time_diff = (reminder.reminder_time - current_time).total_seconds()
                    
                    if -1 <= time_diff <= 0:  # Allow 1-second buffer for precision
                        reminders_to_send.append(reminder)
                        reminder.notification_sent = True
                        logger.info(f"Reminder triggered for event {event_id} at {current_time}")
            
            # Send reminders outside the lock to avoid blocking
            for reminder in reminders_to_send:
                await self._send_event_reminder(reminder)
                
        except Exception as e:
            logger.error(f"Error in precise reminder loop: {e}")
    
    async def add_event_reminder(self, event_data: Dict[str, Any]) -> bool:
        """
        Add an event reminder to the system.
        
        Args:
            event_data: Event data dictionary containing event details
            
        Returns:
            True if reminder was added successfully
        """
        try:
            event_id = event_data.get('id')
            if not event_id:
                logger.error("Event ID is required for reminder")
                return False
            
            # Parse event date
            event_date = event_data.get('event_date')
            if isinstance(event_date, str):
                try:
                    event_date = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                except ValueError:
                    logger.error(f"Invalid event date format: {event_date}")
                    return False
            elif not isinstance(event_date, datetime):
                logger.error(f"Event date must be datetime or ISO string: {type(event_date)}")
                return False
            
            # Calculate reminder time
            reminder_hours = event_data.get('reminder_hours_before', 24)
            reminder_time = event_date - timedelta(hours=reminder_hours)
            
            # Don't add reminders for past events or past reminder times
            current_time = datetime.now()
            if event_date <= current_time:
                logger.info(f"Event {event_id} is in the past, not adding reminder")
                return False
            
            if reminder_time <= current_time:
                logger.info(f"Reminder time for event {event_id} has passed, not adding reminder")
                return False
            
            # Create reminder event
            reminder = ReminderEvent(
                event_id=event_id,
                guild_id=event_data.get('guild_id'),
                event_name=event_data.get('event_name', 'Unknown Event'),
                event_date=event_date,
                reminder_time=reminder_time,
                reminder_hours_before=reminder_hours,
                created_by_id=event_data.get('created_by_id')
            )
            
            async with self._lock:
                self.active_reminders[event_id] = reminder
            
            logger.info(f"Added reminder for event '{reminder.event_name}' (ID: {event_id}) "
                       f"to trigger at {reminder_time} ({reminder_hours} hours before event)")
            return True
            
        except Exception as e:
            logger.error(f"Error adding event reminder: {e}")
            return False
    
    async def remove_event_reminder(self, event_id: int) -> bool:
        """
        Remove an event reminder from the system.
        
        Args:
            event_id: Event ID to remove reminder for
            
        Returns:
            True if reminder was removed successfully
        """
        try:
            async with self._lock:
                if event_id in self.active_reminders:
                    del self.active_reminders[event_id]
                    logger.info(f"Removed reminder for event {event_id}")
                    return True
                else:
                    logger.warning(f"No reminder found for event {event_id}")
                    return False
        except Exception as e:
            logger.error(f"Error removing event reminder: {e}")
            return False
    
    async def update_event_reminder(self, event_data: Dict[str, Any]) -> bool:
        """
        Update an existing event reminder with new data.
        
        Args:
            event_data: Updated event data
            
        Returns:
            True if reminder was updated successfully
        """
        try:
            event_id = event_data.get('id')
            if not event_id:
                return False
            
            # Remove existing reminder and add updated one
            await self.remove_event_reminder(event_id)
            return await self.add_event_reminder(event_data)
            
        except Exception as e:
            logger.error(f"Error updating event reminder: {e}")
            return False
    
    async def get_active_reminders(self) -> Dict[int, ReminderEvent]:
        """Get all active reminders"""
        async with self._lock:
            return self.active_reminders.copy()
    
    async def refresh_reminders_from_database(self):
        """Refresh reminders from database (called on bot startup)"""
        try:
            if not hasattr(self.bot, 'db'):
                logger.warning("Bot database not available for reminder refresh")
                return
            
            # Get all events needing reminders
            events_needing_reminders = await self.bot.db.get_events_needing_reminders()
            
            async with self._lock:
                self.active_reminders.clear()
            
            added_count = 0
            for event in events_needing_reminders:
                if await self.add_event_reminder(event):
                    added_count += 1
            
            logger.info(f"Refreshed {added_count} event reminders from database")
            
        except Exception as e:
            logger.error(f"Error refreshing reminders from database: {e}")
    
    async def _send_event_reminder(self, reminder: ReminderEvent):
        """
        Send reminder notification for an event.
        
        Args:
            reminder: ReminderEvent to send reminder for
        """
        try:
            # Get the event cog to handle reminder sending
            event_cog = self.bot.get_cog('EventSystem')
            if not event_cog:
                logger.error("EventSystem cog not found, cannot send reminder")
                return
            
            # Get full event data from database
            event_data = await self.bot.db.get_event_by_id(reminder.event_id)
            if not event_data:
                logger.error(f"Event {reminder.event_id} not found in database")
                return
            
            # Get guild
            guild = self.bot.get_guild(reminder.guild_id)
            if not guild:
                logger.error(f"Guild {reminder.guild_id} not found")
                return
            
            # Get all invited users for this event
            invitations = await self.bot.db.get_event_invitations(reminder.event_id)
            
            reminder_sent_count = 0
            for invitation in invitations:
                try:
                    user = self.bot.get_user(invitation['user_id'])
                    if user:
                        await self._send_individual_reminder(user, event_data, reminder)
                        reminder_sent_count += 1
                        
                        # Small delay to avoid rate limits
                        await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error sending reminder to user {invitation['user_id']}: {e}")
            
            # Mark reminder as sent in database
            await self.bot.db.mark_reminder_sent(reminder.event_id)
            
            logger.info(f"Sent {reminder_sent_count} reminder notifications for event '{reminder.event_name}'")
            
        except Exception as e:
            logger.error(f"Error sending event reminder: {e}")
    
    async def _send_individual_reminder(self, user: discord.User, event_data: Dict[str, Any], reminder: ReminderEvent):
        """
        Send individual reminder DM to a user.
        
        Args:
            user: Discord user to send reminder to
            event_data: Event data dictionary
            reminder: ReminderEvent object
        """
        try:
            embed = discord.Embed(
                title="🔔 Event Reminder",
                description=f"**{event_data['event_name']}** is coming up soon!",
                color=0xFFD700
            )
            
            if event_data.get('description'):
                embed.add_field(name="Description", value=event_data['description'], inline=False)
            
            # Use smart time formatter for event date
            if event_data.get('event_date'):
                event_time_str = SmartTimeFormatter.format_event_datetime(event_data['event_date'])
                embed.add_field(name="Event Time", value=event_time_str, inline=False)
            
            if event_data.get('location'):
                embed.add_field(name="Location", value=event_data['location'], inline=False)
            
            # Add time until event
            if event_data.get('event_date'):
                time_until = SmartTimeFormatter.format_time_until_event(event_data['event_date'])
                embed.add_field(name="Starts", value=time_until, inline=True)
            
            embed.set_footer(text=f"Reminder sent {reminder.reminder_hours_before} hours before the event")
            embed.timestamp = datetime.now()
            
            await user.send(embed=embed)
            logger.debug(f"Sent reminder DM to {user.display_name} for event {reminder.event_id}")
            
        except discord.Forbidden:
            logger.warning(f"Cannot send DM to {user.display_name} (DMs disabled)")
        except Exception as e:
            logger.error(f"Error sending individual reminder to {user.display_name}: {e}")
    
    async def cleanup_old_reminders(self):
        """Remove reminders for events that have already occurred"""
        try:
            current_time = datetime.now()
            to_remove = []
            
            async with self._lock:
                for event_id, reminder in self.active_reminders.items():
                    # Remove reminders for events that have passed
                    if reminder.event_date <= current_time:
                        to_remove.append(event_id)
                
                for event_id in to_remove:
                    del self.active_reminders[event_id]
            
            if to_remove:
                logger.info(f"Cleaned up {len(to_remove)} old reminders")
                
        except Exception as e:
            logger.error(f"Error cleaning up old reminders: {e}")
    
    def register_callback(self, event_type: str, callback: Callable):
        """
        Register a callback for reminder events.
        
        Args:
            event_type: Type of event to register callback for
            callback: Async callable to execute
        """
        self.reminder_callbacks[event_type] = callback
        logger.info(f"Registered callback for {event_type} reminder events")
    
    async def get_reminder_stats(self) -> Dict[str, Any]:
        """Get statistics about the reminder system"""
        try:
            async with self._lock:
                total_reminders = len(self.active_reminders)
                pending_reminders = sum(1 for r in self.active_reminders.values() if not r.notification_sent)
                sent_reminders = total_reminders - pending_reminders
            
            return {
                'is_running': self.is_running,
                'total_reminders': total_reminders,
                'pending_reminders': pending_reminders,
                'sent_reminders': sent_reminders,
                'loop_running': not self.precise_reminder_loop.failed()
            }
            
        except Exception as e:
            logger.error(f"Error getting reminder stats: {e}")
            return {'error': str(e)}
    
    @precise_reminder_loop.before_loop
    async def before_reminder_loop(self):
        """Wait for bot to be ready before starting loop"""
        await self.bot.wait_until_ready()
        logger.info("Bot ready, starting precise reminder system")
    
    @precise_reminder_loop.error
    async def reminder_loop_error(self, error):
        """Handle errors in the reminder loop"""
        logger.error(f"Error in precise reminder loop: {error}")
        # Restart the loop after a delay
        await asyncio.sleep(5)
        if not self.precise_reminder_loop.is_running():
            self.precise_reminder_loop.restart()
