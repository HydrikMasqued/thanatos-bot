import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

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
            re.compile(r'(\d+\.?\d*)\s*([a-zA-Z]+)', re.IGNORECASE),
            # Pattern for just number (assume hours as default)
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
        
        # Split by common separators and parse each part
        parts = re.split(r'[,\s]+', duration_str)
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
        
        # Try pattern matching
        for pattern in self.patterns:
            match = pattern.match(component)
            if match:
                if len(match.groups()) == 1:
                    # Just a number, assume hours
                    value = float(match.group(1))
                    return timedelta(hours=value), f"{value} hour{'s' if value != 1 else ''}"
                else:
                    # Number with unit
                    value = float(match.group(1))
                    unit_str = match.group(2).lower()
                    
                    # Find the unit
                    unit = self._normalize_unit(unit_str)
                    if unit:
                        delta, normalized = self._create_timedelta(value, unit)
                        return delta, normalized
        
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
