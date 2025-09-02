import re
import pytz
from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Any
import logging

logger = logging.getLogger(__name__)

class SmartTimeFormatter:
    """
    Unified time formatting utility with Discord timestamp integration,
    natural language parsing, and multi-language support.
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
    def parse_natural_language_time(text: str, base_time: Optional[datetime] = None) -> Optional[datetime]:
        """
        Parse natural language time expressions into datetime objects.
        
        Args:
            text: Natural language time expression
            base_time: Base datetime to calculate relative times from
        
        Returns:
            Parsed datetime object or None if parsing fails
        """
        if not text:
            return None
            
        if base_time is None:
            base_time = datetime.now()
        
        text = text.strip().lower()
        
        # Handle "now" expressions
        if SmartTimeFormatter.TIME_PATTERNS['now'].search(text) or \
           SmartTimeFormatter.TIME_PATTERNS['right_now'].search(text) or \
           SmartTimeFormatter.TIME_PATTERNS['immediately'].search(text):
            return base_time
        
        # Handle "in X hours/minutes/seconds/days"
        for pattern_name, pattern in SmartTimeFormatter.TIME_PATTERNS.items():
            if pattern_name.startswith('in_x_'):
                match = pattern.search(text)
                if match:
                    amount = int(match.group(1))
                    if 'hours' in pattern_name:
                        return base_time + timedelta(hours=amount)
                    elif 'minutes' in pattern_name:
                        return base_time + timedelta(minutes=amount)
                    elif 'seconds' in pattern_name:
                        return base_time + timedelta(seconds=amount)
                    elif 'days' in pattern_name:
                        return base_time + timedelta(days=amount)
        
        # Handle "today at X" or "today in X"
        today_at_match = SmartTimeFormatter.TIME_PATTERNS['today_at'].search(text)
        if today_at_match:
            hour = int(today_at_match.group(1))
            minute = int(today_at_match.group(2)) if today_at_match.group(2) else 0
            period = today_at_match.group(3)
            
            if period and period.lower() == 'pm' and hour != 12:
                hour += 12
            elif period and period.lower() == 'am' and hour == 12:
                hour = 0
            
            return base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        today_in_match = SmartTimeFormatter.TIME_PATTERNS['today_in'].search(text)
        if today_in_match:
            amount = int(today_in_match.group(1))
            unit = today_in_match.group(2).lower()
            
            if 'hour' in unit:
                return base_time + timedelta(hours=amount)
            elif 'minute' in unit or 'min' in unit:
                return base_time + timedelta(minutes=amount)
        
        # Handle "tomorrow at X" or "tomorrow in X"
        tomorrow_at_match = SmartTimeFormatter.TIME_PATTERNS['tomorrow_at'].search(text)
        if tomorrow_at_match:
            hour = int(tomorrow_at_match.group(1))
            minute = int(tomorrow_at_match.group(2)) if tomorrow_at_match.group(2) else 0
            period = tomorrow_at_match.group(3)
            
            if period and period.lower() == 'pm' and hour != 12:
                hour += 12
            elif period and period.lower() == 'am' and hour == 12:
                hour = 0
            
            tomorrow = base_time + timedelta(days=1)
            return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        tomorrow_in_match = SmartTimeFormatter.TIME_PATTERNS['tomorrow_in'].search(text)
        if tomorrow_in_match:
            amount = int(tomorrow_in_match.group(1))
            unit = tomorrow_in_match.group(2).lower()
            
            tomorrow_start = base_time + timedelta(days=1)
            tomorrow_start = tomorrow_start.replace(hour=0, minute=0, second=0, microsecond=0)
            
            if 'hour' in unit:
                return tomorrow_start + timedelta(hours=amount)
            elif 'minute' in unit or 'min' in unit:
                return tomorrow_start + timedelta(minutes=amount)
        
        # Handle weekdays
        next_weekday_match = SmartTimeFormatter.TIME_PATTERNS['next_weekday'].search(text)
        if next_weekday_match:
            weekday_name = next_weekday_match.group(1).lower()
            target_weekday = SmartTimeFormatter.WEEKDAYS.get(weekday_name)
            if target_weekday is not None:
                days_ahead = target_weekday - base_time.weekday()
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                return base_time + timedelta(days=days_ahead)
        
        this_weekday_match = SmartTimeFormatter.TIME_PATTERNS['this_weekday'].search(text)
        if this_weekday_match:
            weekday_name = this_weekday_match.group(1).lower()
            target_weekday = SmartTimeFormatter.WEEKDAYS.get(weekday_name)
            if target_weekday is not None:
                days_ahead = target_weekday - base_time.weekday()
                if days_ahead < 0:  # Target day already passed this week
                    days_ahead += 7
                return base_time + timedelta(days=days_ahead)
        
        return None
    
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
    def get_timezone_aware_datetime(dt: datetime, timezone_str: str = 'UTC') -> datetime:
        """
        Convert datetime to timezone-aware datetime.
        
        Args:
            dt: datetime object
            timezone_str: Timezone string (e.g., 'UTC', 'US/Eastern')
        
        Returns:
            Timezone-aware datetime
        """
        try:
            tz = pytz.timezone(timezone_str)
            if dt.tzinfo is None:
                return tz.localize(dt)
            else:
                return dt.astimezone(tz)
        except Exception as e:
            logger.error(f"Error converting timezone: {e}")
            return dt
    
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
            if dt.tzinfo and now.tzinfo is None:
                now = pytz.UTC.localize(now)
            elif dt.tzinfo is None and now.tzinfo:
                dt = pytz.UTC.localize(dt)
            
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
    def parse_natural_duration(duration_str: str, start_time: Optional[datetime] = None) -> tuple[datetime, str]:
        """
        Parse natural language duration strings and return end time and normalized duration.
        
        Args:
            duration_str: Duration string like "2 weeks", "3 days", "1 month", etc.
            start_time: Starting time (defaults to now)
        
        Returns:
            Tuple of (end_time, normalized_duration_string)
        
        Raises:
            ValueError: If the duration string cannot be parsed
        """
        if start_time is None:
            start_time = datetime.now()
        
        if not duration_str:
            raise ValueError("Duration cannot be empty")
        
        duration_str = duration_str.strip().lower()
        
        # Define time unit mappings
        time_units = {
            # Seconds
            's': 'seconds', 'sec': 'seconds', 'second': 'seconds', 'seconds': 'seconds',
            # Minutes  
            'm': 'minutes', 'min': 'minutes', 'minute': 'minutes', 'minutes': 'minutes',
            # Hours
            'h': 'hours', 'hr': 'hours', 'hrs': 'hours', 'hour': 'hours', 'hours': 'hours',
            # Days
            'd': 'days', 'day': 'days', 'days': 'days',
            # Weeks
            'w': 'weeks', 'week': 'weeks', 'weeks': 'weeks',
            # Months
            'mo': 'months', 'month': 'months', 'months': 'months',
            # Years
            'y': 'years', 'yr': 'years', 'yrs': 'years', 'year': 'years', 'years': 'years'
        }
        
        try:
            # Try simple number + unit pattern first
            match = re.match(r'^(\d+(?:\.\d+)?)\s*([a-zA-Z]+)$', duration_str)
            if match:
                value = float(match.group(1))
                unit_str = match.group(2).lower()
                unit = time_units.get(unit_str)
                
                if unit:
                    delta, normalized = SmartTimeFormatter._create_duration_delta(value, unit)
                    end_time = start_time + delta
                    return end_time, normalized
            
            # Try more complex patterns with "and" or commas
            parts = re.split(r'[,\s]+and[,\s]+|,\s*', duration_str)
            total_delta = timedelta()
            parsed_components = []
            
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                    
                match = re.match(r'^(\d+(?:\.\d+)?)\s*([a-zA-Z]+)$', part)
                if match:
                    value = float(match.group(1))
                    unit_str = match.group(2).lower()
                    unit = time_units.get(unit_str)
                    
                    if unit:
                        delta, normalized = SmartTimeFormatter._create_duration_delta(value, unit)
                        total_delta += delta
                        parsed_components.append(normalized)
            
            if parsed_components:
                end_time = start_time + total_delta
                normalized_duration = ' '.join(parsed_components)
                return end_time, normalized_duration
            
            raise ValueError(f"Could not parse duration: '{duration_str}'")
            
        except Exception as e:
            raise ValueError(f"Invalid duration format: '{duration_str}' - {str(e)}")
    
    @staticmethod
    def _create_duration_delta(value: float, unit: str) -> tuple[timedelta, str]:
        """
        Create timedelta and normalized string for a value and unit.
        
        Returns:
            Tuple of (timedelta, normalized_string)
        """
        # Handle plural/singular for display
        display_unit = unit.rstrip('s') if value == 1 else unit
        normalized_str = f"{int(value) if value.is_integer() else value} {display_unit}"
        
        if unit == 'seconds':
            return timedelta(seconds=value), normalized_str
        elif unit == 'minutes':
            return timedelta(minutes=value), normalized_str
        elif unit == 'hours':
            return timedelta(hours=value), normalized_str
        elif unit == 'days':
            return timedelta(days=value), normalized_str
        elif unit == 'weeks':
            return timedelta(weeks=value), normalized_str
        elif unit == 'months':
            # Approximate months as 30.44 days (average month length)
            days = value * 30.44
            return timedelta(days=days), normalized_str
        elif unit == 'years':
            # Approximate years as 365.25 days (accounting for leap years)
            days = value * 365.25
            return timedelta(days=days), normalized_str
        else:
            raise ValueError(f"Unsupported time unit: {unit}")
    
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
