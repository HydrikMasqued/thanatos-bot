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
        
        # Today/Tomorrow patterns
        'today_at': re.compile(r'\btoday\s+(?:at\s+)?(\d{1,2}):?(\d{2})?\s*(am|pm)?\b', re.IGNORECASE),
        'today_in': re.compile(r'\btoday\s+in\s+(\d+)\s+(hours?|minutes?|mins?)\b', re.IGNORECASE),
        'tomorrow_at': re.compile(r'\btomorrow\s+(?:at\s+)?(\d{1,2}):?(\d{2})?\s*(am|pm)?\b', re.IGNORECASE),
        'tomorrow_in': re.compile(r'\btomorrow\s+in\s+(\d+)\s+(hours?|minutes?|mins?)\b', re.IGNORECASE),
        
        # Weekday patterns
        'next_weekday': re.compile(r'\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', re.IGNORECASE),
        'this_weekday': re.compile(r'\bthis\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', re.IGNORECASE),
        
        # Common time expressions
        'now': re.compile(r'\bnow\b', re.IGNORECASE),
        'right_now': re.compile(r'\bright\s+now\b', re.IGNORECASE),
        'immediately': re.compile(r'\bimmediately\b', re.IGNORECASE),
    }
    
    WEEKDAYS = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6
    }
    
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
            timestamp = int(dt.timestamp())
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
            timestamp = int(dt.timestamp())
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
            timestamp = int(dt.timestamp())
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
            timestamp = int(event_time.timestamp())
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
               SmartTimeFormatter.TIME_PATTERNS['immediately'].search(time_str):
                return now
            
            # Handle "in X hours/minutes/days"
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
