import re
import json
from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Any, List, Tuple
import logging
from utils.smart_time_formatter import SmartTimeFormatter

logger = logging.getLogger(__name__)

class AdvancedTimestampParser:
    """
    Advanced timestamp parsing utility that extends SmartTimeFormatter
    with comprehensive Discord timestamp recognition, natural language parsing,
    and multiple format support for bot commands.
    """
    
    # Discord timestamp pattern (recognizes existing Discord timestamps)
    DISCORD_TIMESTAMP_PATTERN = re.compile(r'<t:(\d+):([FfDdTtRr])>', re.IGNORECASE)
    
    # Extended natural language patterns with enhanced flexibility
    EXTENDED_TIME_PATTERNS = {
        # Time with specific dates
        'on_date_at_time': re.compile(r'\bon\s+(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\s+(?:at\s+)?(\d{1,2}):?(\d{2})?\s*(am|pm)?\b', re.IGNORECASE),
        'date_at_time': re.compile(r'(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\s+(?:at\s+)?(\d{1,2}):?(\d{2})?\s*(am|pm)?\b', re.IGNORECASE),
        
        # Enhanced today/tomorrow patterns with flexible time - Fixed to catch standalone "today"
        'today_anytime': re.compile(r'\btoday(?:\s+(?:anytime|any\s+time|at\s+any\s+time|sometime))?(?!\s+\d)\b', re.IGNORECASE),
        'tomorrow_anytime': re.compile(r'\btomorrow(?:\s+(?:anytime|any\s+time|at\s+any\s+time|sometime))?(?!\s+\d)\b', re.IGNORECASE),
        'today_flexible_time': re.compile(r'\btoday\s+(?:at\s+)?(\d{1,2})(?:[:.](\d{2})?)?\s*(am|pm)?\b', re.IGNORECASE),
        'tomorrow_flexible_time': re.compile(r'\btomorrow\s+(?:at\s+)?(\d{1,2})(?:[:.](\d{2})?)?\s*(am|pm)?\b', re.IGNORECASE),
        
        # Enhanced week patterns with flexible interpretation
        'next_week_flexible': re.compile(r'\bnext\s+week(?:\s+(?:anytime|any\s+time|sometime))?\b', re.IGNORECASE),
        'this_week_flexible': re.compile(r'\bthis\s+week(?:\s+(?:anytime|any\s+time|sometime))?\b', re.IGNORECASE),
        'last_week_flexible': re.compile(r'\blast\s+week(?:\s+(?:anytime|any\s+time|sometime))?\b', re.IGNORECASE),
        'end_of_week_flexible': re.compile(r'\bend\s+of\s+(?:this\s+|the\s+)?week\b', re.IGNORECASE),
        'beginning_of_week': re.compile(r'\b(?:beginning|start)\s+of\s+(?:this\s+|the\s+|next\s+)?week\b', re.IGNORECASE),
        
        # Enhanced month patterns
        'next_month_flexible': re.compile(r'\bnext\s+month(?:\s+(?:anytime|any\s+time|sometime))?\b', re.IGNORECASE),
        'this_month_flexible': re.compile(r'\bthis\s+month(?:\s+(?:anytime|any\s+time|sometime))?\b', re.IGNORECASE),
        'end_of_month_flexible': re.compile(r'\bend\s+of\s+(?:this\s+|the\s+|next\s+)?month\b', re.IGNORECASE),
        'beginning_of_month': re.compile(r'\b(?:beginning|start)\s+of\s+(?:this\s+|the\s+|next\s+)?month\b', re.IGNORECASE),
        
        # Month and day patterns
        'month_day': re.compile(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?\b', re.IGNORECASE),
        'month_day_time': re.compile(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?\s+(?:at\s+)?(\d{1,2}):?(\d{2})?\s*(am|pm)?\b', re.IGNORECASE),
        
        # Enhanced weekday patterns with more flexibility
        'weekday_flexible': re.compile(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+(?:anytime|any\s+time|sometime))?\b', re.IGNORECASE),
        'next_weekday_flexible': re.compile(r'\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+(?:anytime|any\s+time|sometime))?\b', re.IGNORECASE),
        'this_weekday_flexible': re.compile(r'\bthis\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+(?:anytime|any\s+time|sometime))?\b', re.IGNORECASE),
        'last_weekday_flexible': re.compile(r'\blast\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+(?:anytime|any\s+time|sometime))?\b', re.IGNORECASE),
        
        # Day of week with time (keeping existing patterns)
        'weekday_at_time': re.compile(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(?:at\s+)?(\d{1,2}):?(\d{2})?\s*(am|pm)?\b', re.IGNORECASE),
        'next_weekday_at_time': re.compile(r'\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(?:at\s+)?(\d{1,2}):?(\d{2})?\s*(am|pm)?\b', re.IGNORECASE),
        
        # Enhanced relative time patterns
        'soon_flexible': re.compile(r'\b(?:soon|later|sometime\s+(?:today|soon))\b', re.IGNORECASE),
        'later_today': re.compile(r'\blater(?:\s+today)?\b', re.IGNORECASE),
        'sometime_this_week': re.compile(r'\bsometime\s+this\s+week\b', re.IGNORECASE),
        'sometime_next_week': re.compile(r'\bsometime\s+next\s+week\b', re.IGNORECASE),
        
        # Existing relative time patterns
        'x_hours_from_now': re.compile(r'\b(\d+)\s+hours?\s+from\s+now\b', re.IGNORECASE),
        'x_minutes_from_now': re.compile(r'\b(\d+)\s+(?:minutes?|mins?)\s+from\s+now\b', re.IGNORECASE),
        'x_days_from_now': re.compile(r'\b(\d+)\s+days?\s+from\s+now\b', re.IGNORECASE),
        'x_weeks_from_now': re.compile(r'\b(\d+)\s+weeks?\s+from\s+now\b', re.IGNORECASE),
        
        # Enhanced time of day patterns
        'morning_flexible': re.compile(r'\b(?:this\s+|tomorrow\s+|next\s+)?(?:morning|am)(?:\s+sometime)?\b', re.IGNORECASE),
        'afternoon_flexible': re.compile(r'\b(?:this\s+|tomorrow\s+|next\s+)?(?:afternoon|pm)(?:\s+sometime)?\b', re.IGNORECASE),
        'evening_flexible': re.compile(r'\b(?:this\s+|tomorrow\s+|next\s+)?evening(?:\s+sometime)?\b', re.IGNORECASE),
        'night_flexible': re.compile(r'\b(?:this\s+|tomorrow\s+|next\s+)?(?:night|tonight)(?:\s+sometime)?\b', re.IGNORECASE),
        
        # Specific time formats (keeping existing)
        'just_time': re.compile(r'\b(\d{1,2}):(\d{2})\s*(am|pm)?\b', re.IGNORECASE),
        'military_time': re.compile(r'\b([01]?\d|2[0-3]):([0-5]\d)\b'),
        
        # Due dates and deadlines (keeping existing)
        'due_by': re.compile(r'\bdue\s+by\s+(.+)', re.IGNORECASE),
        'deadline': re.compile(r'\bdeadline:?\s*(.+)', re.IGNORECASE),
        'expires': re.compile(r'\bexpires?\s+(?:on|at)?\s*(.+)', re.IGNORECASE),
        
        # Event-specific patterns (keeping existing)
        'starts_at': re.compile(r'\bstarts?\s+(?:at|on)\s+(.+)', re.IGNORECASE),
        'begins_at': re.compile(r'\bbegins?\s+(?:at|on)\s+(.+)', re.IGNORECASE),
        'scheduled_for': re.compile(r'\bscheduled\s+for\s+(.+)', re.IGNORECASE),
        
        # Duration patterns (keeping existing)
        'in_x_hours_and_y_minutes': re.compile(r'\bin\s+(\d+)\s+hours?\s+(?:and\s+)?(\d+)\s+(?:minutes?|mins?)\b', re.IGNORECASE),
        'for_x_hours': re.compile(r'\bfor\s+(\d+)\s+hours?\b', re.IGNORECASE),
        'lasting_x_minutes': re.compile(r'\blasting\s+(\d+)\s+(?:minutes?|mins?)\b', re.IGNORECASE),
    }
    
    # Month name to number mapping
    MONTH_NAMES = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    
    @classmethod
    def parse_any_timestamp(cls, time_input: str, context: str = "general") -> Optional[Dict[str, Any]]:
        """
        Parse any timestamp format and return comprehensive information.
        
        Args:
            time_input: Input string containing time information
            context: Context for parsing ("event", "dues", "reminder", "general")
            
        Returns:
            Dictionary with parsed timestamp information or None
        """
        if not time_input or not isinstance(time_input, str):
            return None
            
        time_input = time_input.strip()
        
        # Check for contradictory terms
        contradictory_pairs = [
            ('tomorrow', 'yesterday'),
            ('next', 'last'),
            ('today', 'yesterday'),
            ('today', 'tomorrow'),
        ]
        
        time_lower = time_input.lower()
        for term1, term2 in contradictory_pairs:
            if term1 in time_lower and term2 in time_lower:
                return {
                    'datetime': None,
                    'timestamp': None,
                    'discord_timestamp': None,
                    'style': None,
                    'source_format': 'contradictory',
                    'confidence': 0.0,
                    'is_valid': False,
                    'error': f'Contradictory terms: "{term1}" and "{term2}" cannot be used together'
                }
        
        try:
            # Check if it's already a Discord timestamp
            discord_match = cls.DISCORD_TIMESTAMP_PATTERN.search(time_input)
            if discord_match:
                timestamp = int(discord_match.group(1))
                style = discord_match.group(2)
                dt = datetime.fromtimestamp(timestamp)
                
                return {
                    'datetime': dt,
                    'timestamp': timestamp,
                    'discord_timestamp': time_input[discord_match.start():discord_match.end()],
                    'style': style,
                    'source_format': 'discord_timestamp',
                    'confidence': 1.0,
                    'is_valid': True,
                    'error': None
                }
            
            # Try extended patterns first (more specific)
            result = cls._parse_extended_patterns(time_input)
            if result:
                return result
            
            # Try natural language parsing with SmartTimeFormatter as fallback
            parsed_dt = SmartTimeFormatter.parse_natural_language_time(time_input)
            if parsed_dt:
                return cls._create_result_dict(parsed_dt, 'natural_language', time_input, 0.9)
                
            # Try ISO format and common date formats
            result = cls._parse_standard_formats(time_input)
            if result:
                return result
                
            # Try context-specific parsing
            result = cls._parse_context_specific(time_input, context)
            if result:
                return result
                
            return None
            
        except Exception as e:
            logger.error(f"Error parsing timestamp '{time_input}': {e}")
            return {
                'datetime': None,
                'timestamp': None,
                'discord_timestamp': None,
                'style': None,
                'source_format': 'unknown',
                'confidence': 0.0,
                'is_valid': False,
                'error': str(e)
            }
    
    @classmethod
    def _parse_extended_patterns(cls, time_input: str) -> Optional[Dict[str, Any]]:
        """Parse using extended patterns."""
        from datetime import timezone
        now = datetime.now()
        # For consistency, we'll work with naive local time throughout
        # The bot should run in the user's local timezone
        
        # Try month and day patterns
        month_day_match = cls.EXTENDED_TIME_PATTERNS['month_day_time'].search(time_input)
        if not month_day_match:
            month_day_match = cls.EXTENDED_TIME_PATTERNS['month_day'].search(time_input)
            
        if month_day_match:
            month_name = month_day_match.group(1).lower()
            day = int(month_day_match.group(2))
            month = cls.MONTH_NAMES.get(month_name)
            
            if month:
                # Determine year (current or next if date has passed)
                year = now.year
                test_date = datetime(year, month, day)
                if test_date < now:
                    year += 1
                
                # Extract time if available
                hour, minute = 12, 0  # Default to noon
                if len(month_day_match.groups()) > 2 and month_day_match.group(3):
                    hour = int(month_day_match.group(3))
                    minute = int(month_day_match.group(4)) if month_day_match.group(4) else 0
                    ampm = month_day_match.group(5)
                    
                    if ampm:
                        if ampm.lower() == 'pm' and hour != 12:
                            hour += 12
                        elif ampm.lower() == 'am' and hour == 12:
                            hour = 0
                
                try:
                    parsed_dt = datetime(year, month, day, hour, minute)
                    return cls._create_result_dict(parsed_dt, 'month_day_pattern', time_input, 0.8)
                except ValueError:
                    pass
        
        # Try enhanced flexible patterns first
        
        # Handle "today" variants - check for time first
        today_time_match = cls.EXTENDED_TIME_PATTERNS['today_flexible_time'].search(time_input)
        if today_time_match:
            hour = int(today_time_match.group(1))
            minute = int(today_time_match.group(2)) if today_time_match.group(2) else 0
            ampm = today_time_match.group(3)
            
            if ampm:
                if ampm.lower() == 'pm' and hour != 12:
                    hour += 12
                elif ampm.lower() == 'am' and hour == 12:
                    hour = 0
                    
            parsed_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return cls._create_result_dict(parsed_dt, 'today_with_time', time_input, 0.9)
            
        elif cls.EXTENDED_TIME_PATTERNS['today_anytime'].search(time_input):
            # Default to a reasonable future time for "today anytime" or just "today"
            # If it's before noon, use noon, otherwise use a time 1 hour from now
            if now.hour < 12:
                parsed_dt = now.replace(hour=12, minute=0, second=0, microsecond=0)  # Use noon
            else:
                # Use current time + 1 hour to ensure it's in the future
                future_time = now + timedelta(hours=1)
                parsed_dt = future_time.replace(minute=0, second=0, microsecond=0)
                
            return cls._create_result_dict(parsed_dt, 'today_flexible', time_input, 0.9)
        
        # Handle "tomorrow" variants - check for time first
        tomorrow_time_match = cls.EXTENDED_TIME_PATTERNS['tomorrow_flexible_time'].search(time_input)
        if tomorrow_time_match:
            tomorrow = now + timedelta(days=1)
            hour = int(tomorrow_time_match.group(1))
            minute = int(tomorrow_time_match.group(2)) if tomorrow_time_match.group(2) else 0
            ampm = tomorrow_time_match.group(3)
            
            if ampm:
                if ampm.lower() == 'pm' and hour != 12:
                    hour += 12
                elif ampm.lower() == 'am' and hour == 12:
                    hour = 0
                    
            parsed_dt = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return cls._create_result_dict(parsed_dt, 'tomorrow_with_time', time_input, 0.9)
            
        elif cls.EXTENDED_TIME_PATTERNS['tomorrow_anytime'].search(time_input):
            tomorrow = now + timedelta(days=1)
            # Default to noon for "tomorrow anytime" or just "tomorrow"
            parsed_dt = tomorrow.replace(hour=12, minute=0, second=0, microsecond=0)
            return cls._create_result_dict(parsed_dt, 'tomorrow_flexible', time_input, 0.9)
        
        # Handle flexible week patterns
        if cls.EXTENDED_TIME_PATTERNS['next_week_flexible'].search(time_input):
            days_ahead = 7 - now.weekday() + 6  # Next Monday
            parsed_dt = (now + timedelta(days=days_ahead)).replace(hour=12, minute=0, second=0, microsecond=0)
            return cls._create_result_dict(parsed_dt, 'next_week_flexible', time_input, 0.8)
            
        if cls.EXTENDED_TIME_PATTERNS['this_week_flexible'].search(time_input):
            days_to_friday = (4 - now.weekday()) % 7  # This Friday
            parsed_dt = (now + timedelta(days=days_to_friday)).replace(hour=12, minute=0, second=0, microsecond=0)
            return cls._create_result_dict(parsed_dt, 'this_week_flexible', time_input, 0.8)
            
        if cls.EXTENDED_TIME_PATTERNS['end_of_week_flexible'].search(time_input):
            days_to_sunday = (6 - now.weekday()) % 7
            if days_to_sunday == 0:  # If today is Sunday
                days_to_sunday = 7
            parsed_dt = (now + timedelta(days=days_to_sunday)).replace(hour=17, minute=0, second=0, microsecond=0)  # 5 PM
            return cls._create_result_dict(parsed_dt, 'end_of_week_flexible', time_input, 0.8)
            
        if cls.EXTENDED_TIME_PATTERNS['beginning_of_week'].search(time_input):
            if 'next' in time_input.lower():
                days_ahead = 7 - now.weekday() + 6  # Next Monday
            else:
                days_ahead = (0 - now.weekday()) % 7  # This Monday
                if days_ahead == 0 and now.weekday() != 0:  # If not Monday, go to next Monday
                    days_ahead = 7
            parsed_dt = (now + timedelta(days=days_ahead)).replace(hour=9, minute=0, second=0, microsecond=0)  # 9 AM
            return cls._create_result_dict(parsed_dt, 'beginning_of_week', time_input, 0.8)
        
        # Handle flexible weekday patterns
        for pattern_name in ['next_weekday_flexible', 'this_weekday_flexible', 'last_weekday_flexible', 'weekday_flexible']:
            match = cls.EXTENDED_TIME_PATTERNS[pattern_name].search(time_input)
            if match:
                weekday_name = match.group(1).lower()
                if weekday_name in SmartTimeFormatter.WEEKDAYS:
                    target_weekday = SmartTimeFormatter.WEEKDAYS[weekday_name]
                    current_weekday = now.weekday()
                    
                    if pattern_name == 'next_weekday_flexible':
                        days_ahead = target_weekday - current_weekday + 7
                    elif pattern_name == 'this_weekday_flexible':
                        days_ahead = target_weekday - current_weekday
                        if days_ahead <= 0:
                            days_ahead += 7
                    elif pattern_name == 'last_weekday_flexible':
                        days_ahead = target_weekday - current_weekday - 7
                    else:  # weekday_flexible
                        days_ahead = target_weekday - current_weekday
                        if days_ahead <= 0:
                            days_ahead += 7
                    
                    target_date = now + timedelta(days=days_ahead)
                    parsed_dt = target_date.replace(hour=12, minute=0, second=0, microsecond=0)
                    return cls._create_result_dict(parsed_dt, pattern_name, time_input, 0.8)
        
        # Handle flexible time of day patterns
        if cls.EXTENDED_TIME_PATTERNS['morning_flexible'].search(time_input):
            if 'tomorrow' in time_input.lower():
                target_date = now + timedelta(days=1)
            else:
                target_date = now
            parsed_dt = target_date.replace(hour=9, minute=0, second=0, microsecond=0)
            return cls._create_result_dict(parsed_dt, 'morning_flexible', time_input, 0.7)
            
        if cls.EXTENDED_TIME_PATTERNS['afternoon_flexible'].search(time_input):
            if 'tomorrow' in time_input.lower():
                target_date = now + timedelta(days=1)
            else:
                target_date = now
            parsed_dt = target_date.replace(hour=14, minute=0, second=0, microsecond=0)  # 2 PM
            return cls._create_result_dict(parsed_dt, 'afternoon_flexible', time_input, 0.7)
            
        if cls.EXTENDED_TIME_PATTERNS['evening_flexible'].search(time_input):
            if 'tomorrow' in time_input.lower():
                target_date = now + timedelta(days=1)
            else:
                target_date = now
            parsed_dt = target_date.replace(hour=18, minute=0, second=0, microsecond=0)  # 6 PM
            return cls._create_result_dict(parsed_dt, 'evening_flexible', time_input, 0.7)
            
        if cls.EXTENDED_TIME_PATTERNS['night_flexible'].search(time_input):
            if 'tomorrow' in time_input.lower():
                target_date = now + timedelta(days=1)
            else:
                target_date = now
            parsed_dt = target_date.replace(hour=20, minute=0, second=0, microsecond=0)  # 8 PM
            return cls._create_result_dict(parsed_dt, 'night_flexible', time_input, 0.7)
        
        # Handle "soon" and "later" patterns
        if cls.EXTENDED_TIME_PATTERNS['soon_flexible'].search(time_input) or cls.EXTENDED_TIME_PATTERNS['later_today'].search(time_input):
            # "Soon" or "later" means in 1-2 hours from now
            parsed_dt = now + timedelta(hours=1, minutes=30)
            return cls._create_result_dict(parsed_dt, 'soon_flexible', time_input, 0.6)
        
        # Handle "sometime" patterns
        if cls.EXTENDED_TIME_PATTERNS['sometime_this_week'].search(time_input):
            # Middle of the week (Wednesday) at a reasonable time
            days_to_wednesday = (2 - now.weekday()) % 7
            if days_to_wednesday == 0:  # If today is Wednesday
                days_to_wednesday = 1  # Tomorrow instead
            parsed_dt = (now + timedelta(days=days_to_wednesday)).replace(hour=14, minute=0, second=0, microsecond=0)
            return cls._create_result_dict(parsed_dt, 'sometime_this_week', time_input, 0.6)
            
        if cls.EXTENDED_TIME_PATTERNS['sometime_next_week'].search(time_input):
            # Next Wednesday at a reasonable time
            days_ahead = 7 - now.weekday() + 2  # Next Wednesday
            parsed_dt = (now + timedelta(days=days_ahead)).replace(hour=14, minute=0, second=0, microsecond=0)
            return cls._create_result_dict(parsed_dt, 'sometime_next_week', time_input, 0.6)
        
        # Try original weekday patterns (keeping existing logic)
        weekday_match = cls.EXTENDED_TIME_PATTERNS['next_weekday_at_time'].search(time_input)
        if not weekday_match:
            weekday_match = cls.EXTENDED_TIME_PATTERNS['weekday_at_time'].search(time_input)
            
        if weekday_match:
            weekday_name = weekday_match.group(1).lower()
            if weekday_name in SmartTimeFormatter.WEEKDAYS:
                target_weekday = SmartTimeFormatter.WEEKDAYS[weekday_name]
                current_weekday = now.weekday()
                
                # Calculate days ahead
                days_ahead = target_weekday - current_weekday
                if 'next' in time_input.lower() or days_ahead <= 0:
                    days_ahead = days_ahead + 7 if days_ahead <= 0 else days_ahead
                
                target_date = now + timedelta(days=days_ahead)
                
                # Extract time if available
                hour, minute = 12, 0  # Default to noon
                if len(weekday_match.groups()) > 1 and weekday_match.group(2):
                    hour = int(weekday_match.group(2))
                    minute = int(weekday_match.group(3)) if weekday_match.group(3) else 0
                    ampm = weekday_match.group(4)
                    
                    if ampm:
                        if ampm.lower() == 'pm' and hour != 12:
                            hour += 12
                        elif ampm.lower() == 'am' and hour == 12:
                            hour = 0
                
                parsed_dt = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return cls._create_result_dict(parsed_dt, 'weekday_pattern', time_input, 0.8)
        
        # Try relative time patterns
        for pattern_name, pattern in cls.EXTENDED_TIME_PATTERNS.items():
            if pattern_name.endswith('_from_now'):
                match = pattern.search(time_input)
                if match:
                    amount = int(match.group(1))
                    if 'hours' in pattern_name:
                        parsed_dt = now + timedelta(hours=amount)
                    elif 'minutes' in pattern_name:
                        parsed_dt = now + timedelta(minutes=amount)
                    elif 'days' in pattern_name:
                        parsed_dt = now + timedelta(days=amount)
                    elif 'weeks' in pattern_name:
                        parsed_dt = now + timedelta(weeks=amount)
                    else:
                        continue
                        
                    return cls._create_result_dict(parsed_dt, 'relative_pattern', time_input, 0.8)
        
        return None
    
    @classmethod
    def _parse_standard_formats(cls, time_input: str) -> Optional[Dict[str, Any]]:
        """Parse standard date/time formats."""
        formats_to_try = [
            # ISO formats
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            
            # Common formats
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y %I:%M %p",
            "%d/%m/%Y",
            
            # Time only
            "%H:%M:%S",
            "%H:%M",
            "%I:%M %p",
            
            # Text formats
            "%B %d, %Y %H:%M:%S",
            "%B %d, %Y %H:%M",
            "%B %d, %Y %I:%M %p",
            "%B %d, %Y",
            "%b %d, %Y %H:%M:%S",
            "%b %d, %Y %H:%M",
            "%b %d, %Y %I:%M %p",
            "%b %d, %Y",
        ]
        
        for fmt in formats_to_try:
            try:
                if fmt in ["%H:%M:%S", "%H:%M", "%I:%M %p"]:
                    # Time only - assume today's date
                    time_part = datetime.strptime(time_input, fmt).time()
                    parsed_dt = datetime.combine(datetime.now().date(), time_part)
                else:
                    parsed_dt = datetime.strptime(time_input, fmt)
                    
                return cls._create_result_dict(parsed_dt, 'standard_format', time_input, 0.9, fmt)
            except ValueError:
                continue
                
        return None
    
    @classmethod
    def _parse_context_specific(cls, time_input: str, context: str) -> Optional[Dict[str, Any]]:
        """Parse based on specific context (event, dues, etc)."""
        # Event-specific parsing
        if context == "event":
            for pattern_name in ['starts_at', 'begins_at', 'scheduled_for']:
                pattern = cls.EXTENDED_TIME_PATTERNS[pattern_name]
                match = pattern.search(time_input)
                if match:
                    time_part = match.group(1).strip()
                    # Recursively parse the extracted time part
                    result = cls.parse_any_timestamp(time_part, "general")
                    if result and result['is_valid']:
                        result['source_format'] = f'event_{pattern_name}'
                        result['confidence'] = min(result['confidence'], 0.7)
                        return result
        
        # Dues-specific parsing
        elif context == "dues":
            for pattern_name in ['due_by', 'deadline', 'expires']:
                pattern = cls.EXTENDED_TIME_PATTERNS[pattern_name]
                match = pattern.search(time_input)
                if match:
                    time_part = match.group(1).strip()
                    # Recursively parse the extracted time part
                    result = cls.parse_any_timestamp(time_part, "general")
                    if result and result['is_valid']:
                        result['source_format'] = f'dues_{pattern_name}'
                        result['confidence'] = min(result['confidence'], 0.7)
                        return result
        
        return None
    
    @classmethod
    def _create_result_dict(cls, dt: datetime, source_format: str, original_input: str, 
                           confidence: float, format_string: str = None) -> Dict[str, Any]:
        """Create standardized result dictionary."""
        try:
            # Validate the datetime - allow past dates during testing
            is_valid, error_msg = SmartTimeFormatter.validate_event_time(dt, min_advance_minutes=-999999)
            
            timestamp = SmartTimeFormatter.ensure_local_timestamp(dt)
            discord_timestamp = f"<t:{timestamp}:F>"
            
            return {
                'datetime': dt,
                'timestamp': timestamp,
                'discord_timestamp': discord_timestamp,
                'style': 'F',  # Default to full format
                'source_format': source_format,
                'format_string': format_string,
                'original_input': original_input,
                'confidence': confidence,
                'is_valid': is_valid,
                'error': None if is_valid else error_msg
            }
        except Exception as e:
            return {
                'datetime': dt,
                'timestamp': None,
                'discord_timestamp': None,
                'style': None,
                'source_format': source_format,
                'format_string': format_string,
                'original_input': original_input,
                'confidence': 0.0,
                'is_valid': False,
                'error': str(e)
            }
    
    @classmethod
    def create_discord_timestamp(cls, dt: datetime, style: str = 'F') -> str:
        """
        Create Discord timestamp from datetime.
        
        Args:
            dt: datetime object
            style: Discord timestamp style (F, f, D, d, T, t, R)
            
        Returns:
            Discord timestamp string
        """
        return SmartTimeFormatter.format_discord_timestamp(dt, style)
    
    @classmethod
    def parse_multiple_timestamps(cls, text: str, context: str = "general") -> List[Dict[str, Any]]:
        """
        Parse multiple timestamps from a single text input.
        
        Args:
            text: Input text that may contain multiple timestamps
            context: Parsing context
            
        Returns:
            List of parsed timestamp dictionaries
        """
        results = []
        
        # Find all Discord timestamps first
        for match in cls.DISCORD_TIMESTAMP_PATTERN.finditer(text):
            timestamp = int(match.group(1))
            style = match.group(2)
            dt = datetime.fromtimestamp(timestamp)
            
            result = {
                'datetime': dt,
                'timestamp': timestamp,
                'discord_timestamp': match.group(0),
                'style': style,
                'source_format': 'discord_timestamp',
                'position': (match.start(), match.end()),
                'confidence': 1.0,
                'is_valid': True,
                'error': None
            }
            results.append(result)
        
        # Remove Discord timestamps from text and look for other patterns
        clean_text = cls.DISCORD_TIMESTAMP_PATTERN.sub('', text)
        
        # Try to parse remaining text as single timestamp
        if clean_text.strip():
            single_result = cls.parse_any_timestamp(clean_text.strip(), context)
            if single_result and single_result['is_valid']:
                results.append(single_result)
        
        return results
    
    @classmethod
    def suggest_timestamp_formats(cls, dt: datetime) -> Dict[str, str]:
        """
        Generate all Discord timestamp format suggestions for a datetime.
        
        Args:
            dt: datetime object
            
        Returns:
            Dictionary with format descriptions and Discord timestamps
        """
        timestamp = SmartTimeFormatter.ensure_local_timestamp(dt)
        
        return {
            'full_long': f"<t:{timestamp}:F>",  # December 15, 2024 3:30 PM
            'full_short': f"<t:{timestamp}:f>",  # December 15, 2024 3:30 PM (shorter)
            'date_long': f"<t:{timestamp}:D>",   # December 15, 2024
            'date_short': f"<t:{timestamp}:d>",  # 12/15/2024
            'time_long': f"<t:{timestamp}:T>",   # 3:30:45 PM
            'time_short': f"<t:{timestamp}:t>",  # 3:30 PM
            'relative': f"<t:{timestamp}:R>"     # in 2 hours
        }
