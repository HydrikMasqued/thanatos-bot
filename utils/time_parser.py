import re
from datetime import datetime, timedelta
from typing import Optional, Union, Tuple
import calendar
from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta

class TimeParser:
    """Parse various time formats into datetime objects"""
    
    def __init__(self):
        # Time unit mappings
        self.time_units = {
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
        
        # Compile regex patterns for efficiency
        self.patterns = [
            # Pattern for number + unit (e.g., "5s", "2 weeks", "3months")
            re.compile(r'^(\d+\.?\d*)\s*([a-zA-Z]+)$', re.IGNORECASE),
            # Pattern for just number (require explicit unit - don't assume)
            re.compile(r'^(\d+\.?\d*)$')
        ]
    
    def parse_duration(self, duration_str: str, start_time: Optional[datetime] = None) -> Tuple[datetime, str]:
        """
        Parse a duration string and return the end time and normalized duration string
        
        Args:
            duration_str: String like "5s", "2 weeks", "3 months", etc.
            start_time: Starting time (defaults to now)
            
        Returns:
            Tuple of (end_time, normalized_duration_string)
            
        Raises:
            ValueError: If the duration string cannot be parsed
        """
        if start_time is None:
            start_time = datetime.now()
        
        duration_str = duration_str.strip().lower()
        
        if not duration_str:
            raise ValueError("Duration cannot be empty")
        
        # Try to parse the duration
        total_delta = None
        parsed_components = []
        
        # Handle common time formats first before splitting
        # Check if it's a single time expression like "2 seconds" or "5 minutes"
        single_match = re.match(r'^(\d+\.?\d*)\s+([a-zA-Z]+)$', duration_str, re.IGNORECASE)
        if single_match:
            # This is a single time expression like "5 seconds"
            value = float(single_match.group(1))
            unit_str = single_match.group(2).lower()
            unit = self._normalize_unit(unit_str)
            if unit:
                delta, normalized = self._create_timedelta(value, unit)
                return start_time + delta, normalized
        
        # Split by common separators and parse each part
        parts = re.split(r'[,]+', duration_str)  # Split only on commas, not spaces
        parts = [part.strip() for part in parts if part.strip()]
        
        for part in parts:
            component_delta, component_str = self._parse_single_component(part)
            if component_delta:
                if total_delta is None:
                    total_delta = component_delta
                else:
                    total_delta += component_delta
                parsed_components.append(component_str)
        
        if total_delta is None:
            raise ValueError(f"Could not parse duration: '{duration_str}'")
        
        # Calculate end time
        end_time = start_time + total_delta
        
        # Create normalized duration string
        normalized_duration = ' '.join(parsed_components)
        
        return end_time, normalized_duration
    
    def _parse_single_component(self, component: str) -> Tuple[Optional[timedelta], str]:
        """
        Parse a single component like "5s" or "2 weeks"
        
        Returns:
            Tuple of (timedelta, normalized_string)
        """
        component = component.strip().lower()
        
        # First try the number + unit pattern
        match = self.patterns[0].match(component)
        if match:
            # Number with unit
            value = float(match.group(1))
            unit_str = match.group(2).lower()
            
            # Find the unit
            unit = self._normalize_unit(unit_str)
            if unit:
                delta, normalized = self._create_timedelta(value, unit)
                return delta, normalized
        
        # Then try just number pattern
        match = self.patterns[1].match(component)
        if match:
            # Just a number - reject it, require explicit unit
            raise ValueError(f"Time duration '{component}' must include a unit (s, m, h, d, w, mo, y)")
        
        return None, ""
    
    def _normalize_unit(self, unit_str: str) -> Optional[str]:
        """Normalize unit string to standard form"""
        unit_str = unit_str.lower().strip()
        return self.time_units.get(unit_str)
    
    def _create_timedelta(self, value: float, unit: str) -> Tuple[timedelta, str]:
        """
        Create timedelta and normalized string for a value and unit
        
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
            delta = timedelta(days=days)
            return delta, normalized_str
        elif unit == 'years':
            # Approximate years as 365.25 days (accounting for leap years)
            days = value * 365.25
            delta = timedelta(days=days)
            return delta, normalized_str
        else:
            raise ValueError(f"Unsupported time unit: {unit}")
    
    def format_time_remaining(self, end_time: datetime, current_time: Optional[datetime] = None) -> str:
        """
        Format the time remaining until end_time in a human-readable way
        
        Args:
            end_time: The target end time
            current_time: Current time (defaults to now)
            
        Returns:
            Formatted string like "2 days, 3 hours remaining" or "Expired 1 hour ago"
        """
        if current_time is None:
            current_time = datetime.now()
        
        delta = end_time - current_time
        
        if delta.total_seconds() < 0:
            # Already expired
            delta = current_time - end_time
            return f"Expired {self._format_delta(delta)} ago"
        else:
            return f"{self._format_delta(delta)} remaining"
    
    def _format_delta(self, delta: timedelta) -> str:
        """Format a timedelta into human-readable format"""
        total_seconds = int(abs(delta.total_seconds()))
        
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        parts = []
        
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0 and days == 0:  # Only show minutes if less than a day
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds > 0 and days == 0 and hours == 0:  # Only show seconds if less than an hour
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
        
        if not parts:
            return "0 seconds"
        
        if len(parts) == 1:
            return parts[0]
        elif len(parts) == 2:
            return f"{parts[0]} and {parts[1]}"
        else:
            return f"{', '.join(parts[:-1])}, and {parts[-1]}"
    
    def is_valid_duration(self, duration_str: str) -> bool:
        """
        Check if a duration string is valid without raising an exception
        
        Args:
            duration_str: Duration string to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            self.parse_duration(duration_str)
            return True
        except (ValueError, Exception):
            return False
    
    def parse_event_reminder_time(self, reminder_str: str, event_time: datetime) -> datetime:
        """
        Parse event reminder time string aggressively.
        Supports formats like:
        - "30s", "5m", "1h" (before event)
        - "in 30 seconds", "in an hour"
        - "30 seconds", "5 minutes", "1 hour"
        
        Args:
            reminder_str: Reminder time string (e.g., "1h", "30 minutes")
            event_time: The event datetime
            
        Returns:
            datetime when reminder should be sent
            
        Raises:
            ValueError: If the reminder string cannot be parsed
        """
        reminder_str = reminder_str.strip().lower()
        
        if not reminder_str:
            raise ValueError("Reminder time cannot be empty")
        
        # Remove common prefixes that don't change meaning
        reminder_str = re.sub(r'^(in\s+|before\s+)', '', reminder_str)
        
        # Parse the duration
        try:
            # Use existing duration parsing but treat as "before event"
            duration_delta, _ = self.parse_duration(reminder_str, datetime.now())
            duration_only = duration_delta - datetime.now()
            
            # Calculate reminder time (before the event)
            reminder_time = event_time - duration_only
            
            # Ensure reminder time is not in the past
            now = datetime.now()
            if reminder_time <= now:
                # If calculated time is in the past, set to immediate future
                reminder_time = now + timedelta(seconds=5)
            
            return reminder_time
            
        except Exception as e:
            # Try alternative parsing for common phrases
            alt_result = self._parse_alternative_reminder_formats(reminder_str, event_time)
            if alt_result:
                return alt_result
            
            raise ValueError(f"Could not parse reminder time: '{reminder_str}'. Use formats like '30s', '5m', '1h', '2 hours', etc.")
    
    def _parse_alternative_reminder_formats(self, reminder_str: str, event_time: datetime) -> Optional[datetime]:
        """
        Parse alternative reminder formats
        """
        now = datetime.now()
        
        # Handle "X before" patterns
        before_match = re.match(r'(\d+\.?\d*)\s*([a-zA-Z]+)\s+before', reminder_str)
        if before_match:
            try:
                value = float(before_match.group(1))
                unit_str = before_match.group(2)
                unit = self._normalize_unit(unit_str)
                if unit:
                    delta, _ = self._create_timedelta(value, unit)
                    reminder_time = event_time - delta
                    return reminder_time if reminder_time > now else now + timedelta(seconds=5)
            except:
                pass
        
        # Handle "an hour", "a minute" etc.
        article_match = re.match(r'an?\s+([a-zA-Z]+)', reminder_str)
        if article_match:
            unit_str = article_match.group(1)
            unit = self._normalize_unit(unit_str)
            if unit:
                delta, _ = self._create_timedelta(1.0, unit)
                reminder_time = event_time - delta
                return reminder_time if reminder_time > now else now + timedelta(seconds=5)
        
        return None
    
    def calculate_hourly_reminders(self, event_time: datetime, start_time: Optional[datetime] = None) -> list[datetime]:
        """
        Calculate hourly reminder times leading up to an event.
        
        Args:
            event_time: When the event occurs
            start_time: When to start sending reminders (defaults to now)
            
        Returns:
            List of datetime objects when reminders should be sent
        """
        if start_time is None:
            start_time = datetime.now()
        
        reminders = []
        
        # Don't send reminders for events in the past
        if event_time <= start_time:
            return reminders
        
        # Calculate time until event
        time_until_event = event_time - start_time
        hours_until_event = time_until_event.total_seconds() / 3600
        
        # Send reminders every hour, starting from next hour mark
        current_time = start_time
        
        # Round up to next hour
        next_hour = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        reminder_time = next_hour
        while reminder_time < event_time:
            reminders.append(reminder_time)
            reminder_time += timedelta(hours=1)
        
        # Always add a final reminder 15 minutes before if event is more than 15 minutes away
        final_reminder = event_time - timedelta(minutes=15)
        if final_reminder > start_time and final_reminder not in reminders:
            reminders.append(final_reminder)
        
        # Sort reminders chronologically
        reminders.sort()
        
        return reminders
    
    def get_precise_time_until(self, target_time: datetime, current_time: Optional[datetime] = None) -> dict:
        """
        Get precise time remaining until target with aggressive accuracy.
        
        Args:
            target_time: Target datetime
            current_time: Current time (defaults to now)
            
        Returns:
            Dict with precise time breakdown and total seconds
        """
        if current_time is None:
            current_time = datetime.now()
        
        delta = target_time - current_time
        total_seconds = delta.total_seconds()
        
        if total_seconds <= 0:
            return {
                'is_past': True,
                'total_seconds': abs(total_seconds),
                'days': 0, 'hours': 0, 'minutes': 0, 'seconds': 0,
                'formatted': 'Event has passed'
            }
        
        # Calculate components
        days = int(total_seconds // 86400)
        remaining_seconds = total_seconds % 86400
        hours = int(remaining_seconds // 3600)
        remaining_seconds = remaining_seconds % 3600
        minutes = int(remaining_seconds // 60)
        seconds = int(remaining_seconds % 60)
        
        # Format string
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")
        
        return {
            'is_past': False,
            'total_seconds': total_seconds,
            'days': days,
            'hours': hours, 
            'minutes': minutes,
            'seconds': seconds,
            'formatted': ' '.join(parts)
        }
    
    def parse_natural_datetime(self, text: str) -> Optional[datetime]:
        """
        Parse natural language date/time expressions into datetime objects.
        
        Supports formats like:
        - "today 8pm", "tomorrow 3:30pm", "tonight"
        - "next friday 7pm", "monday at 2pm"
        - "jan 15 8pm", "march 3rd 2024 5:30pm"
        - "in 2 hours", "in 30 minutes"
        - "8pm today", "3pm tomorrow"
        - ISO formats: "2024-01-15 20:00"
        
        Args:
            text: Natural language date/time string
            
        Returns:
            datetime object or None if parsing failed
        """
        if not text or not text.strip():
            return None
        
        text = text.strip().lower()
        now = datetime.now()
        
        try:
            # First, try to handle relative expressions
            relative_result = self._parse_relative_expressions(text, now)
            if relative_result:
                return relative_result
            
            # Handle "today/tonight/tomorrow" with times
            today_result = self._parse_today_tomorrow_expressions(text, now)
            if today_result:
                return today_result
            
            # Handle day names (monday, tuesday, etc.) with times
            day_result = self._parse_day_name_expressions(text, now)
            if day_result:
                return day_result
            
            # Handle specific dates with times
            date_result = self._parse_date_expressions(text, now)
            if date_result:
                return date_result
            
            # Try dateutil parser as fallback (handles many formats)
            try:
                parsed = dateutil_parser.parse(text, default=now)
                # Only accept if it's not just the current time (dateutil defaults)
                if parsed != now:
                    return parsed
            except:
                pass
            
            # Last resort: try to extract time from text and apply to today
            time_result = self._extract_time_for_today(text, now)
            if time_result:
                return time_result
                
        except Exception as e:
            pass  # Continue to return None
        
        return None
    
    def _parse_relative_expressions(self, text: str, now: datetime) -> Optional[datetime]:
        """Parse relative expressions like 'in 2 hours', 'in 30 minutes'"""
        # Match patterns like "in X time_unit"
        in_pattern = re.match(r'in\s+(\d+\.?\d*)\s*([a-z]+)', text)
        if in_pattern:
            try:
                value = float(in_pattern.group(1))
                unit_str = in_pattern.group(2)
                unit = self._normalize_unit(unit_str)
                if unit:
                    delta, _ = self._create_timedelta(value, unit)
                    return now + delta
            except:
                pass
        
        return None
    
    def _parse_today_tomorrow_expressions(self, text: str, now: datetime) -> Optional[datetime]:
        """Parse expressions like 'today 8pm', 'tomorrow 3:30', 'tonight'"""
        # Handle "tonight" (assume 8 PM today)
        if text in ['tonight', 'tonite']:
            return now.replace(hour=20, minute=0, second=0, microsecond=0)
        
        # Handle "today" or "tomorrow" with time
        today_match = re.search(r'(today|tomorrow)(?:\s+(?:at\s+)?(.+))?', text)
        if today_match:
            day_word = today_match.group(1)
            time_part = today_match.group(2)
            
            # Determine the base date
            if day_word == 'today':
                base_date = now.date()
            else:  # tomorrow
                base_date = (now + timedelta(days=1)).date()
            
            # Parse time if provided
            if time_part:
                parsed_time = self._parse_time_string(time_part.strip())
                if parsed_time:
                    return datetime.combine(base_date, parsed_time)
            else:
                # Default to current time of day for "today" or noon for "tomorrow"
                if day_word == 'today':
                    return datetime.combine(base_date, now.time().replace(second=0, microsecond=0))
                else:
                    return datetime.combine(base_date, datetime.min.time().replace(hour=12))
        
        # Handle time followed by today/tomorrow (e.g., "8pm today")
        reverse_match = re.search(r'(.+?)\s+(today|tomorrow)', text)
        if reverse_match:
            time_part = reverse_match.group(1).strip()
            day_word = reverse_match.group(2)
            
            parsed_time = self._parse_time_string(time_part)
            if parsed_time:
                if day_word == 'today':
                    base_date = now.date()
                else:  # tomorrow
                    base_date = (now + timedelta(days=1)).date()
                
                return datetime.combine(base_date, parsed_time)
        
        return None
    
    def _parse_day_name_expressions(self, text: str, now: datetime) -> Optional[datetime]:
        """Parse expressions like 'monday 8pm', 'next friday 2:30'"""
        day_names = {
            'monday': 0, 'mon': 0,
            'tuesday': 1, 'tue': 1, 'tues': 1,
            'wednesday': 2, 'wed': 2,
            'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
            'friday': 4, 'fri': 4,
            'saturday': 5, 'sat': 5,
            'sunday': 6, 'sun': 6
        }
        
        # Try to match day name patterns
        day_pattern = re.search(r'(?:(next|this)\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)(?:\s+(?:at\s+)?(.+))?', text)
        if day_pattern:
            next_this = day_pattern.group(1)  # "next" or "this" or None
            day_name = day_pattern.group(2)
            time_part = day_pattern.group(3)
            
            target_weekday = day_names.get(day_name)
            if target_weekday is not None:
                # Find the next occurrence of this day
                current_weekday = now.weekday()
                days_ahead = target_weekday - current_weekday
                
                # Handle "next" vs "this" vs no qualifier
                if next_this == 'next':
                    if days_ahead <= 0:
                        days_ahead += 7
                elif next_this == 'this':
                    if days_ahead < 0:
                        days_ahead += 7
                else:
                    # No qualifier - use next occurrence (including today if it's the same day)
                    if days_ahead < 0:
                        days_ahead += 7
                    elif days_ahead == 0:  # Same day
                        # If time is specified and it's in the future today, use today
                        # Otherwise use next week
                        if time_part:
                            parsed_time = self._parse_time_string(time_part.strip())
                            if parsed_time:
                                test_datetime = datetime.combine(now.date(), parsed_time)
                                if test_datetime <= now:
                                    days_ahead = 7
                        else:
                            days_ahead = 7  # Default to next week if no time specified
                
                target_date = (now + timedelta(days=days_ahead)).date()
                
                # Parse time if provided
                if time_part:
                    parsed_time = self._parse_time_string(time_part.strip())
                    if parsed_time:
                        return datetime.combine(target_date, parsed_time)
                else:
                    # Default to noon
                    return datetime.combine(target_date, datetime.min.time().replace(hour=12))
        
        return None
    
    def _parse_date_expressions(self, text: str, now: datetime) -> Optional[datetime]:
        """Parse specific date expressions like 'jan 15 8pm', 'march 3rd 2024 5:30pm'"""
        month_names = {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12
        }
        
        # Try various date patterns
        patterns = [
            # "jan 15", "january 15th", "jan 15 2024", etc. with optional time
            re.compile(r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s+(\d{4}))?(?:\s+(?:at\s+)?(.+))?', re.IGNORECASE),
            # "15 jan", "15th january", "15 jan 2024", etc. with optional time
            re.compile(r'(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)(?:\s+(\d{4}))?(?:\s+(?:at\s+)?(.+))?', re.IGNORECASE),
            # ISO-like: "2024-01-15", "01-15-2024", "01/15/2024" with optional time
            re.compile(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:\s+(?:at\s+)?(.+))?'),
            re.compile(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})(?:\s+(?:at\s+)?(.+))?'),
        ]
        
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                try:
                    groups = match.groups()
                    
                    # Parse based on pattern type
                    if pattern == patterns[0]:  # month day [year] [time]
                        month_str = groups[0].lower()
                        day = int(groups[1])
                        year = int(groups[2]) if groups[2] else now.year
                        time_str = groups[3]
                        month = month_names.get(month_str)
                        
                    elif pattern == patterns[1]:  # day month [year] [time]
                        day = int(groups[0])
                        month_str = groups[1].lower()
                        year = int(groups[2]) if groups[2] else now.year
                        time_str = groups[3]
                        month = month_names.get(month_str)
                        
                    elif pattern == patterns[2]:  # YYYY-MM-DD [time]
                        year = int(groups[0])
                        month = int(groups[1])
                        day = int(groups[2])
                        time_str = groups[3]
                        
                    elif pattern == patterns[3]:  # MM-DD-YYYY [time]
                        month = int(groups[0])
                        day = int(groups[1])
                        year = int(groups[2])
                        time_str = groups[3]
                    
                    else:
                        continue
                    
                    # Validate date
                    if month and 1 <= month <= 12 and 1 <= day <= 31:
                        try:
                            base_date = datetime(year, month, day).date()
                            
                            # Parse time if provided
                            if time_str:
                                parsed_time = self._parse_time_string(time_str.strip())
                                if parsed_time:
                                    return datetime.combine(base_date, parsed_time)
                            
                            # Default to noon if no time
                            return datetime.combine(base_date, datetime.min.time().replace(hour=12))
                            
                        except ValueError:
                            continue  # Invalid date
                    
                except (ValueError, AttributeError):
                    continue
        
        return None
    
    def _extract_time_for_today(self, text: str, now: datetime) -> Optional[datetime]:
        """Extract time from text and apply to today's date"""
        parsed_time = self._parse_time_string(text)
        if parsed_time:
            return datetime.combine(now.date(), parsed_time)
        return None
    
    def _parse_time_string(self, time_str: str) -> Optional[datetime.time]:
        """Parse various time formats into time object"""
        time_str = time_str.strip().lower()
        
        # Common time patterns
        patterns = [
            # 12-hour format with am/pm
            re.compile(r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$'),
            # 24-hour format
            re.compile(r'^(\d{1,2}):(\d{2})$'),
            # Just hour (assume PM if >= 8, AM otherwise, but after 12 use 24-hour)
            re.compile(r'^(\d{1,2})$'),
        ]
        
        for pattern in patterns:
            match = pattern.match(time_str)
            if match:
                try:
                    groups = match.groups()
                    
                    if pattern == patterns[0]:  # 12-hour with am/pm
                        hour = int(groups[0])
                        minute = int(groups[1]) if groups[1] else 0
                        ampm = groups[2]
                        
                        # Convert to 24-hour
                        if ampm == 'am':
                            if hour == 12:
                                hour = 0
                        else:  # pm
                            if hour != 12:
                                hour += 12
                        
                        if 0 <= hour <= 23 and 0 <= minute <= 59:
                            return datetime.min.time().replace(hour=hour, minute=minute)
                    
                    elif pattern == patterns[1]:  # 24-hour format
                        hour = int(groups[0])
                        minute = int(groups[1])
                        
                        if 0 <= hour <= 23 and 0 <= minute <= 59:
                            return datetime.min.time().replace(hour=hour, minute=minute)
                    
                    elif pattern == patterns[2]:  # Just hour
                        hour = int(groups[0])
                        
                        # Smart hour interpretation
                        if hour <= 12:
                            # For hours 1-7, assume PM (evening events)
                            # For hours 8-12, keep as-is (could be AM or PM)
                            if 1 <= hour <= 7:
                                if hour != 12:  # Don't modify 12
                                    hour += 12
                        
                        if 0 <= hour <= 23:
                            return datetime.min.time().replace(hour=hour, minute=0)
                    
                except (ValueError, AttributeError):
                    continue
        
        # Handle special time words
        special_times = {
            'noon': datetime.min.time().replace(hour=12),
            'midnight': datetime.min.time().replace(hour=0),
            'morning': datetime.min.time().replace(hour=9),
            'afternoon': datetime.min.time().replace(hour=14),
            'evening': datetime.min.time().replace(hour=18),
            'night': datetime.min.time().replace(hour=20),
        }
        
        return special_times.get(time_str)
    
    def format_natural_datetime(self, dt: datetime) -> str:
        """Format datetime in a natural, readable way"""
        now = datetime.now()
        
        # Calculate the difference
        delta = dt.date() - now.date()
        days_diff = delta.days
        
        # Determine day description
        if days_diff == 0:
            day_desc = "Today"
        elif days_diff == 1:
            day_desc = "Tomorrow"
        elif days_diff == -1:
            day_desc = "Yesterday"
        elif 0 < days_diff <= 7:
            day_desc = dt.strftime("%A")  # Day name
        elif days_diff > 7:
            if dt.year == now.year:
                day_desc = dt.strftime("%B %d")  # Month day
            else:
                day_desc = dt.strftime("%B %d, %Y")  # Month day, year
        else:  # Past dates
            if dt.year == now.year:
                day_desc = dt.strftime("%B %d")
            else:
                day_desc = dt.strftime("%B %d, %Y")
        
        # Format time
        time_desc = dt.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ')
        if time_desc.endswith(':00 AM') or time_desc.endswith(':00 PM'):
            time_desc = time_desc[:-6] + time_desc[-3:]  # Remove :00
        
        return f"{day_desc} at {time_desc}"

# Example usage and testing
if __name__ == "__main__":
    parser = TimeParser()
    
    # Test various formats
    test_cases = [
        "5s", "5 seconds", "2m", "2 minutes", "3h", "3 hours",
        "2d", "2 days", "1w", "1 week", "3 weeks", 
        "2mo", "2 months", "1y", "1 year",
        "2 weeks 3 days", "1 month 2 weeks", "5"
    ]
    
    print("Testing time parser:")
    for case in test_cases:
        try:
            end_time, normalized = parser.parse_duration(case)
            remaining = parser.format_time_remaining(end_time)
            print(f"'{case}' -> '{normalized}' -> {remaining}")
        except ValueError as e:
            print(f"'{case}' -> ERROR: {e}")
