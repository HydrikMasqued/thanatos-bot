from datetime import datetime, timedelta
import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

def parse_time_duration(duration_str: str) -> Optional[datetime]:
    """
    Parse a human-readable time duration and return a datetime object.
    
    Supported formats:
    - "1 day", "2 days", "1d"
    - "1 week", "2 weeks", "1w"
    - "1 hour", "2 hours", "1h"
    - "30 minutes", "30 mins", "30m"
    - "1 month" (treated as 30 days)
    - "1 year" (treated as 365 days)
    
    Args:
        duration_str: Human-readable duration string
        
    Returns:
        datetime: The calculated future datetime, or None if parsing fails
    """
    try:
        duration_str = duration_str.lower().strip()
        
        # Define time unit patterns and their conversions to seconds
        patterns = [
            (r'(\d+)\s*(?:years?|y)', 365 * 24 * 3600),  # years
            (r'(\d+)\s*(?:months?|mo)', 30 * 24 * 3600),  # months (30 days)
            (r'(\d+)\s*(?:weeks?|w)', 7 * 24 * 3600),     # weeks
            (r'(\d+)\s*(?:days?|d)', 24 * 3600),          # days
            (r'(\d+)\s*(?:hours?|hrs?|h)', 3600),         # hours
            (r'(\d+)\s*(?:minutes?|mins?|m)', 60),        # minutes
            (r'(\d+)\s*(?:seconds?|secs?|s)', 1),         # seconds
        ]
        
        total_seconds = 0
        
        for pattern, unit_seconds in patterns:
            matches = re.findall(pattern, duration_str)
            for match in matches:
                total_seconds += int(match) * unit_seconds
        
        if total_seconds == 0:
            logger.warning(f"Could not parse duration: {duration_str}")
            return None
        
        return datetime.now() + timedelta(seconds=total_seconds)
        
    except Exception as e:
        logger.error(f"Error parsing time duration '{duration_str}': {e}")
        return None

def parse_absolute_date(date_str: str) -> Optional[datetime]:
    """
    Parse an absolute date string and return a datetime object.
    
    Supported formats:
    - "YYYY-MM-DD"
    - "MM/DD/YYYY"
    - "DD/MM/YYYY" (European format)
    - "YYYY-MM-DD HH:MM"
    - "MM/DD/YYYY HH:MM"
    
    Args:
        date_str: Date string to parse
        
    Returns:
        datetime: The parsed datetime, or None if parsing fails
    """
    try:
        date_str = date_str.strip()
        
        # Common date formats to try
        formats = [
            "%Y-%m-%d %H:%M",     # 2023-12-25 15:30
            "%Y-%m-%d %H:%M:%S",  # 2023-12-25 15:30:00
            "%Y-%m-%d",           # 2023-12-25
            "%m/%d/%Y %H:%M",     # 12/25/2023 15:30
            "%m/%d/%Y",           # 12/25/2023
            "%d/%m/%Y %H:%M",     # 25/12/2023 15:30 (European)
            "%d/%m/%Y",           # 25/12/2023 (European)
            "%B %d, %Y",          # December 25, 2023
            "%B %d, %Y %H:%M",    # December 25, 2023 15:30
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse absolute date: {date_str}")
        return None
        
    except Exception as e:
        logger.error(f"Error parsing absolute date '{date_str}': {e}")
        return None

def parse_date_or_duration(input_str: str) -> Optional[datetime]:
    """
    Parse either a relative duration or absolute date string.
    
    Args:
        input_str: String to parse (can be duration like "1 week" or date like "2023-12-25")
        
    Returns:
        datetime: The parsed/calculated datetime, or None if parsing fails
    """
    try:
        input_str = input_str.strip()
        
        # Try to parse as absolute date first
        result = parse_absolute_date(input_str)
        if result:
            return result
        
        # If that fails, try to parse as duration
        result = parse_time_duration(input_str)
        if result:
            return result
        
        logger.warning(f"Could not parse date or duration: {input_str}")
        return None
        
    except Exception as e:
        logger.error(f"Error parsing date or duration '{input_str}': {e}")
        return None

def format_duration(seconds: int) -> str:
    """
    Format a duration in seconds to a human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        str: Human-readable duration string
    """
    try:
        if seconds < 60:
            return f"{seconds} second{'s' if seconds != 1 else ''}"
        
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        
        hours = minutes // 60
        if hours < 24:
            remaining_minutes = minutes % 60
            if remaining_minutes > 0:
                return f"{hours} hour{'s' if hours != 1 else ''} and {remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}"
            return f"{hours} hour{'s' if hours != 1 else ''}"
        
        days = hours // 24
        remaining_hours = hours % 24
        if remaining_hours > 0:
            return f"{days} day{'s' if days != 1 else ''} and {remaining_hours} hour{'s' if remaining_hours != 1 else ''}"
        return f"{days} day{'s' if days != 1 else ''}"
        
    except Exception as e:
        logger.error(f"Error formatting duration {seconds}: {e}")
        return f"{seconds} seconds"

def get_time_until(target_date: datetime) -> Tuple[int, str]:
    """
    Get the time remaining until a target date.
    
    Args:
        target_date: Target datetime
        
    Returns:
        Tuple[int, str]: (seconds_remaining, human_readable_string)
    """
    try:
        now = datetime.now()
        
        if target_date <= now:
            return 0, "Overdue"
        
        diff = target_date - now
        seconds = int(diff.total_seconds())
        
        return seconds, format_duration(seconds)
        
    except Exception as e:
        logger.error(f"Error calculating time until {target_date}: {e}")
        return 0, "Error"

def is_overdue(target_date: datetime) -> bool:
    """
    Check if a target date has passed.
    
    Args:
        target_date: Target datetime to check
        
    Returns:
        bool: True if the date has passed, False otherwise
    """
    try:
        return datetime.now() > target_date
    except Exception as e:
        logger.error(f"Error checking if overdue {target_date}: {e}")
        return False

# Convenience functions for common durations
def get_date_in_days(days: int) -> datetime:
    """Get a datetime object for a number of days from now"""
    return datetime.now() + timedelta(days=days)

def get_date_in_weeks(weeks: int) -> datetime:
    """Get a datetime object for a number of weeks from now"""
    return datetime.now() + timedelta(weeks=weeks)

def get_date_in_hours(hours: int) -> datetime:
    """Get a datetime object for a number of hours from now"""
    return datetime.now() + timedelta(hours=hours)

# Common validation functions
def validate_future_date(date_obj: datetime, max_days_ahead: int = 365) -> bool:
    """
    Validate that a date is in the future and within reasonable limits.
    
    Args:
        date_obj: Datetime to validate
        max_days_ahead: Maximum days in the future allowed
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        now = datetime.now()
        max_future = now + timedelta(days=max_days_ahead)
        
        return now < date_obj <= max_future
        
    except Exception as e:
        logger.error(f"Error validating future date {date_obj}: {e}")
        return False
