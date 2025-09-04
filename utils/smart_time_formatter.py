import re
from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Any
import logging

logger = logging.getLogger(__name__)

class SmartTimeFormatter:
    """
    Simplified time formatting utility with Discord timestamp integration
    and natural language parsing (without pytz dependency).
    """
    
    # Natural language time patterns
    TIME_PATTERNS = {
        # Relative times
        'in_x_hours': re.compile(r'\bin\s+(\d+)\s+hours?\b', re.IGNORECASE),
        'in_x_minutes': re.compile(r'\bin\s+(\d+)\s+(?:minutes?|mins?)\b', re.IGNORECASE),
        'in_x_seconds': re.compile(r'\bin\s+(\d+)\s+(?:seconds?|secs?)\b', re.IGNORECASE),
        'in_x_days': re.compile(r'\bin\s+(\d+)\s+days?\b', re.IGNORECASE),
        'in_x_weeks': re.compile(r'\bin\s+(\d+)\s+weeks?\b', re.IGNORECASE),
        'in_x_months': re.compile(r'\bin\s+(\d+)\s+months?\b', re.IGNORECASE),
        
        # Today/Tomorrow patterns
        'today': re.compile(r'\btoday\b', re.IGNORECASE),
        'tomorrow': re.compile(r'\btomorrow\b', re.IGNORECASE),
        'yesterday': re.compile(r'\byesterday\b', re.IGNORECASE),
        'today_at': re.compile(r'\btoday\s+(?:at\s+)?(\d{1,2}):?(\d{2})?\s*(am|pm)?\b', re.IGNORECASE),
        'today_in': re.compile(r'\btoday\s+in\s+(\d+)\s+(hours?|minutes?|mins?)\b', re.IGNORECASE),
        'tomorrow_at': re.compile(r'\btomorrow\s+(?:at\s+)?(\d{1,2}):?(\d{2})?\s*(am|pm)?\b', re.IGNORECASE),
        'tomorrow_in': re.compile(r'\btomorrow\s+in\s+(\d+)\s+(hours?|minutes?|mins?)\b', re.IGNORECASE),
        
        # Week patterns
        'next_week': re.compile(r'\bnext\s+week\b', re.IGNORECASE),
        'this_week': re.compile(r'\bthis\s+week\b', re.IGNORECASE),
        'last_week': re.compile(r'\blast\s+week\b', re.IGNORECASE),
        'next_x_weeks': re.compile(r'\bnext\s+(\d+)\s+weeks?\b', re.IGNORECASE),
        
        # Month patterns
        'next_month': re.compile(r'\bnext\s+month\b', re.IGNORECASE),
        'this_month': re.compile(r'\bthis\s+month\b', re.IGNORECASE),
        'last_month': re.compile(r'\blast\s+month\b', re.IGNORECASE),
        
        # Weekday patterns
        'next_weekday': re.compile(r'\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', re.IGNORECASE),
        'this_weekday': re.compile(r'\bthis\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', re.IGNORECASE),
        'last_weekday': re.compile(r'\blast\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', re.IGNORECASE),
        
        # End of time period patterns
        'end_of_week': re.compile(r'\bend\s+of\s+(?:the\s+)?week\b', re.IGNORECASE),
        'end_of_month': re.compile(r'\bend\s+of\s+(?:the\s+)?month\b', re.IGNORECASE),
        'end_of_day': re.compile(r'\bend\s+of\s+(?:the\s+)?day\b', re.IGNORECASE),
        
        # Common time expressions
        'now': re.compile(r'\bnow\b', re.IGNORECASE),
        'right_now': re.compile(r'\bright\s+now\b', re.IGNORECASE),
        'immediately': re.compile(r'\bimmediately\b', re.IGNORECASE),
        'asap': re.compile(r'\basap\b', re.IGNORECASE),
        'soon': re.compile(r'\bsoon\b', re.IGNORECASE),
    }
    
    WEEKDAYS = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6
    }
    
    @staticmethod
    def ensure_local_timestamp(dt: datetime) -> int:
        """
        Ensure datetime is properly converted to Unix timestamp for consistent display.
        
        Args:
            dt: datetime object (naive or aware)
            
        Returns:
            Unix timestamp as integer
        """
        try:
            # If datetime is naive, assume it's local time
            if dt.tzinfo is None:
                # Get current timezone offset and apply it
                import time
                local_offset = time.timezone if time.daylight == 0 else time.altzone
                # Adjust timestamp to account for local timezone
                timestamp = int(dt.timestamp())
                return timestamp
            else:
                # If datetime is timezone-aware, use it directly
                return int(dt.timestamp())
        except Exception as e:
            logger.error(f"Error creating local timestamp: {e}")
            # Fallback: use timestamp() method
            return int(dt.timestamp())
    
    @staticmethod
    def format_discord_timestamp(dt: datetime, style: str = 'F') -> str:
        """
        Format datetime as Discord timestamp with specified style.
        
        Args:
            dt: datetime object to format
            style: Discord timestamp style
                - 'F': Full date/time (December 15, 2024 3:30 PM)
                - 'R': Relative time (in 2 hours)
                - 'f': Short date/time (December 15, 2024 3:30 PM)
                - 'D': Date only (12/15/2024)
                - 't': Time only (3:30 PM)
                - 'T': Time with seconds (3:30:45 PM)
                - 'd': Short date (12/15/2024)
        
        Returns:
            Discord timestamp string
        """
        try:
            timestamp = SmartTimeFormatter.ensure_local_timestamp(dt)
            return f"<t:{timestamp}:{style}>"
        except Exception as e:
            logger.error(f"Error formatting Discord timestamp: {e}")
            return dt.strftime("%B %d, %Y at %I:%M %p")
    
    @staticmethod
    def format_event_datetime(dt: datetime, include_relative: bool = True) -> str:
        """
        Format event datetime with both absolute and relative times.
        
        Args:
            dt: datetime object
            include_relative: Whether to include relative time
        
        Returns:
            Formatted datetime string
        """
        try:
            timestamp = SmartTimeFormatter.ensure_local_timestamp(dt)
            if include_relative:
                return f"<t:{timestamp}:F> (<t:{timestamp}:R>)"
            else:
                return f"<t:{timestamp}:F>"
        except Exception as e:
            logger.error(f"Error formatting event datetime: {e}")
            return dt.strftime("%B %d, %Y at %I:%M %p")
    
    @staticmethod
    def format_reminder_time(dt: datetime) -> str:
        """Format time specifically for reminders."""
        try:
            timestamp = SmartTimeFormatter.ensure_local_timestamp(dt)
            return f"<t:{timestamp}:R>"
        except Exception as e:
            logger.error(f"Error formatting reminder time: {e}")
            return dt.strftime("%I:%M %p")
    
    @staticmethod
    def format_duration(start_time: datetime, end_time: datetime) -> str:
        """
        Format duration between two times in a human-readable way.
        
        Args:
            start_time: Start datetime
            end_time: End datetime
        
        Returns:
            Human-readable duration string
        """
        try:
            delta = end_time - start_time
            
            if delta.total_seconds() < 0:
                return "Event has passed"
            
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            parts = []
            if days > 0:
                parts.append(f"{days} day{'s' if days != 1 else ''}")
            if hours > 0:
                parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
            if minutes > 0:
                parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
            
            if not parts:
                return "Less than a minute"
            
            if len(parts) == 1:
                return parts[0]
            elif len(parts) == 2:
                return f"{parts[0]} and {parts[1]}"
            else:
                return f"{', '.join(parts[:-1])}, and {parts[-1]}"
        except Exception as e:
            logger.error(f"Error formatting duration: {e}")
            return "Unknown duration"
    
    @staticmethod
    def is_time_in_past(dt: datetime, buffer_seconds: int = 0) -> bool:
        """
        Check if datetime is in the past with optional buffer.
        
        Args:
            dt: datetime to check
            buffer_seconds: Buffer seconds to consider
        
        Returns:
            True if time is in the past
        """
        try:
            now = datetime.now()
            return dt < (now - timedelta(seconds=buffer_seconds))
        except Exception as e:
            logger.error(f"Error checking if time is in past: {e}")
            return False
    
    @staticmethod
    def format_time_until_event(event_time: datetime, current_time: Optional[datetime] = None) -> str:
        """
        Format time remaining until an event in a user-friendly way.
        
        Args:
            event_time: Event datetime
            current_time: Current datetime (defaults to now)
        
        Returns:
            Formatted time until event string
        """
        if current_time is None:
            current_time = datetime.now()
        
        try:
            if SmartTimeFormatter.is_time_in_past(event_time):
                return "Event has passed"
            
            # Use Discord relative timestamp for live updating
            timestamp = SmartTimeFormatter.ensure_local_timestamp(event_time)
            return f"<t:{timestamp}:R>"
        except Exception as e:
            logger.error(f"Error formatting time until event: {e}")
            return "Unknown time"
    
    @staticmethod
    def parse_natural_language_time(time_str: str) -> Optional[datetime]:
        """
        Parse natural language time expressions into datetime objects.
        
        Args:
            time_str: Natural language time string
            
        Returns:
            Parsed datetime object or None if parsing fails
        """
        if not time_str:
            return None
            
        time_str = time_str.strip().lower()
        now = datetime.now()
        
        try:
            # Handle "now" and immediate expressions
            if SmartTimeFormatter.TIME_PATTERNS['now'].search(time_str) or \
               SmartTimeFormatter.TIME_PATTERNS['right_now'].search(time_str) or \
               SmartTimeFormatter.TIME_PATTERNS['immediately'].search(time_str) or \
               SmartTimeFormatter.TIME_PATTERNS['asap'].search(time_str) or \
               SmartTimeFormatter.TIME_PATTERNS['soon'].search(time_str):
                return now
            
            # Handle simple day expressions
            if SmartTimeFormatter.TIME_PATTERNS['today'].search(time_str):
                return now.replace(hour=12, minute=0, second=0, microsecond=0)
            elif SmartTimeFormatter.TIME_PATTERNS['tomorrow'].search(time_str):
                return (now + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
            elif SmartTimeFormatter.TIME_PATTERNS['yesterday'].search(time_str):
                return (now - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
            
            # Handle "next week", "this week", etc.
            if SmartTimeFormatter.TIME_PATTERNS['next_week'].search(time_str):
                days_ahead = 7 - now.weekday() + 6  # Next Monday
                return (now + timedelta(days=days_ahead)).replace(hour=12, minute=0, second=0, microsecond=0)
            elif SmartTimeFormatter.TIME_PATTERNS['this_week'].search(time_str):
                days_to_friday = (4 - now.weekday()) % 7  # This Friday
                return (now + timedelta(days=days_to_friday)).replace(hour=12, minute=0, second=0, microsecond=0)
            elif SmartTimeFormatter.TIME_PATTERNS['last_week'].search(time_str):
                days_back = now.weekday() + 7  # Last Monday
                return (now - timedelta(days=days_back)).replace(hour=12, minute=0, second=0, microsecond=0)
            
            # Handle "next month", "this month", etc.
            if SmartTimeFormatter.TIME_PATTERNS['next_month'].search(time_str):
                if now.month == 12:
                    next_month = now.replace(year=now.year + 1, month=1, day=1)
                else:
                    next_month = now.replace(month=now.month + 1, day=1)
                return next_month.replace(hour=12, minute=0, second=0, microsecond=0)
            elif SmartTimeFormatter.TIME_PATTERNS['this_month'].search(time_str):
                end_of_month = now.replace(day=28) + timedelta(days=4)  # Go to next month
                end_of_month = end_of_month - timedelta(days=end_of_month.day)  # Back to last day of current month
                return end_of_month.replace(hour=12, minute=0, second=0, microsecond=0)
            elif SmartTimeFormatter.TIME_PATTERNS['last_month'].search(time_str):
                if now.month == 1:
                    last_month = now.replace(year=now.year - 1, month=12, day=1)
                else:
                    last_month = now.replace(month=now.month - 1, day=1)
                return last_month.replace(hour=12, minute=0, second=0, microsecond=0)
            
            # Handle "end of week/month/day"
            if SmartTimeFormatter.TIME_PATTERNS['end_of_week'].search(time_str):
                days_to_sunday = (6 - now.weekday()) % 7
                return (now + timedelta(days=days_to_sunday)).replace(hour=23, minute=59, second=59, microsecond=0)
            elif SmartTimeFormatter.TIME_PATTERNS['end_of_month'].search(time_str):
                next_month = now.replace(day=28) + timedelta(days=4)
                end_of_month = next_month - timedelta(days=next_month.day)
                return end_of_month.replace(hour=23, minute=59, second=59, microsecond=0)
            elif SmartTimeFormatter.TIME_PATTERNS['end_of_day'].search(time_str):
                return now.replace(hour=23, minute=59, second=59, microsecond=0)
            
            # Handle "in X hours/minutes/days/weeks/months"
            for pattern_name, pattern in SmartTimeFormatter.TIME_PATTERNS.items():
                if pattern_name.startswith('in_x_'):
                    match = pattern.search(time_str)
                    if match:
                        amount = int(match.group(1))
                        if 'hours' in pattern_name:
                            return now + timedelta(hours=amount)
                        elif 'minutes' in pattern_name:
                            return now + timedelta(minutes=amount)
                        elif 'seconds' in pattern_name:
                            return now + timedelta(seconds=amount)
                        elif 'days' in pattern_name:
                            return now + timedelta(days=amount)
                        elif 'weeks' in pattern_name:
                            return now + timedelta(weeks=amount)
                        elif 'months' in pattern_name:
                            # Approximate months as 30 days
                            return now + timedelta(days=amount * 30)
            
            # Handle "today at X" or "tomorrow at X"
            today_match = SmartTimeFormatter.TIME_PATTERNS['today_at'].search(time_str)
            tomorrow_match = SmartTimeFormatter.TIME_PATTERNS['tomorrow_at'].search(time_str)
            
            if today_match or tomorrow_match:
                match = today_match or tomorrow_match
                hour = int(match.group(1))
                minute = int(match.group(2)) if match.group(2) else 0
                ampm = match.group(3)
                
                if ampm:
                    if ampm.lower() == 'pm' and hour != 12:
                        hour += 12
                    elif ampm.lower() == 'am' and hour == 12:
                        hour = 0
                
                target_date = now.date()
                if tomorrow_match:
                    target_date = (now + timedelta(days=1)).date()
                
                return datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute))
            
            # Handle weekday expressions
            for pattern_name in ['next_weekday', 'this_weekday']:
                match = SmartTimeFormatter.TIME_PATTERNS[pattern_name].search(time_str)
                if match:
                    weekday_name = match.group(1).lower()
                    target_weekday = SmartTimeFormatter.WEEKDAYS[weekday_name]
                    current_weekday = now.weekday()
                    
                    if pattern_name == 'next_weekday':
                        days_ahead = target_weekday - current_weekday + 7
                    else:  # this_weekday
                        days_ahead = target_weekday - current_weekday
                        if days_ahead <= 0:
                            days_ahead += 7
                    
                    target_date = now + timedelta(days=days_ahead)
                    return target_date.replace(hour=12, minute=0, second=0, microsecond=0)
            
            # Try common date formats
            date_formats = [
                "%Y-%m-%d",
                "%m/%d/%Y",
                "%d/%m/%Y",
                "%Y-%m-%d %H:%M",
                "%m/%d/%Y %H:%M",
                "%d/%m/%Y %H:%M",
                "%Y-%m-%d %I:%M %p",
                "%m/%d/%Y %I:%M %p",
                "%d/%m/%Y %I:%M %p"
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(time_str, fmt)
                except ValueError:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing natural language time '{time_str}': {e}")
            return None
    
    @staticmethod
    def validate_event_time(dt: datetime, min_advance_minutes: int = 5) -> tuple[bool, str]:
        """
        Validate if an event time is acceptable.
        
        Args:
            dt: Event datetime
            min_advance_minutes: Minimum minutes in advance required
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            now = datetime.now()
            min_time = now + timedelta(minutes=min_advance_minutes)
            
            if dt < min_time:
                return False, f"Event must be scheduled at least {min_advance_minutes} minutes in advance"
            
            # Check if it's too far in the future (1 year)
            max_time = now + timedelta(days=365)
            if dt > max_time:
                return False, "Event cannot be scheduled more than 1 year in advance"
            
            return True, "Valid event time"
        except Exception as e:
            logger.error(f"Error validating event time: {e}")
            return False, "Invalid datetime format"
