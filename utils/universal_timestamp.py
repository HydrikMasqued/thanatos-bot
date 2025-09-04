"""
Universal Timestamp Utility - Bot-wide Natural Language Time Parsing
Provides easy access to advanced timestamp parsing throughout the entire bot.
"""

from typing import Optional, Dict, Any, List, Union
from datetime import datetime
import logging
from utils.advanced_timestamp_parser import AdvancedTimestampParser
from utils.smart_time_formatter import SmartTimeFormatter

logger = logging.getLogger(__name__)

class UniversalTimestamp:
    """
    Universal timestamp utility that provides easy access to advanced timestamp 
    parsing and formatting throughout the entire Thanatos Bot.
    
    This class serves as a simplified interface to the advanced timestamp system,
    making it easy for any cog or module to parse natural language time expressions.
    """
    
    @staticmethod
    def parse(time_input: str, context: str = "general") -> Optional[Dict[str, Any]]:
        """
        Parse any natural language time expression into a structured result.
        
        Args:
            time_input: Natural language time string (e.g., "tomorrow", "next week", "today anytime")
            context: Parsing context ("event", "dues", "reminder", "general")
            
        Returns:
            Dictionary with parsed information or None if parsing fails
            
        Examples:
            >>> UniversalTimestamp.parse("tomorrow 8pm")
            {'datetime': datetime(...), 'discord_timestamp': '<t:...:F>', 'confidence': 0.9, ...}
            
            >>> UniversalTimestamp.parse("next week anytime")  
            {'datetime': datetime(...), 'discord_timestamp': '<t:...:F>', 'confidence': 0.8, ...}
        """
        try:
            return AdvancedTimestampParser.parse_any_timestamp(time_input, context)
        except Exception as e:
            logger.error(f"Error parsing timestamp '{time_input}': {e}")
            return None
    
    @staticmethod  
    def parse_simple(time_input: str, context: str = "general") -> Optional[datetime]:
        """
        Simple timestamp parsing that returns just the datetime object.
        
        Args:
            time_input: Natural language time string
            context: Parsing context
            
        Returns:
            datetime object or None if parsing fails
            
        Examples:
            >>> UniversalTimestamp.parse_simple("tomorrow")
            datetime(2025, 9, 5, 12, 0)
            
            >>> UniversalTimestamp.parse_simple("today anytime")
            datetime(2025, 9, 4, 19, 20, 15)
        """
        result = UniversalTimestamp.parse(time_input, context)
        return result['datetime'] if result and result.get('is_valid') else None
    
    @staticmethod
    def to_discord(dt: datetime, style: str = 'F') -> str:
        """
        Convert datetime to Discord timestamp format.
        
        Args:
            dt: datetime object
            style: Discord timestamp style (F, f, D, d, T, t, R)
            
        Returns:
            Discord timestamp string
            
        Examples:
            >>> UniversalTimestamp.to_discord(datetime.now(), 'R')
            '<t:1725908415:R>'  # Shows as "in 2 hours" in Discord
        """
        return AdvancedTimestampParser.create_discord_timestamp(dt, style)
    
    @staticmethod
    def format_flexible(dt: datetime, include_relative: bool = True) -> str:
        """
        Format datetime with both absolute and relative Discord timestamps.
        
        Args:
            dt: datetime object
            include_relative: Whether to include relative time
            
        Returns:
            Formatted string with Discord timestamps
            
        Examples:
            >>> UniversalTimestamp.format_flexible(datetime.now())
            '<t:1725908415:F> (<t:1725908415:R>)'
        """
        return SmartTimeFormatter.format_event_datetime(dt, include_relative)
    
    @staticmethod
    def get_all_formats(dt: datetime) -> Dict[str, str]:
        """
        Get all Discord timestamp format options for a datetime.
        
        Args:
            dt: datetime object
            
        Returns:
            Dictionary with all format options
            
        Examples:
            >>> formats = UniversalTimestamp.get_all_formats(datetime.now())
            >>> formats['relative']  # '<t:1725908415:R>'
            >>> formats['full_long']  # '<t:1725908415:F>'
        """
        return AdvancedTimestampParser.suggest_timestamp_formats(dt)
    
    @staticmethod
    def parse_multiple(text: str, context: str = "general") -> List[Dict[str, Any]]:
        """
        Parse multiple timestamps from a single text input.
        
        Args:
            text: Text containing multiple time expressions
            context: Parsing context
            
        Returns:
            List of parsed timestamp dictionaries
        """
        return AdvancedTimestampParser.parse_multiple_timestamps(text, context)
    
    @staticmethod
    def is_valid_time(time_input: str, context: str = "general") -> bool:
        """
        Check if a time string can be parsed successfully.
        
        Args:
            time_input: Time string to validate
            context: Parsing context
            
        Returns:
            True if the time string is valid and parseable
            
        Examples:
            >>> UniversalTimestamp.is_valid_time("tomorrow 8pm")
            True
            >>> UniversalTimestamp.is_valid_time("invalid time")
            False
        """
        result = UniversalTimestamp.parse(time_input, context)
        return result is not None and result.get('is_valid', False)
    
    @staticmethod
    def get_examples() -> Dict[str, List[str]]:
        """
        Get examples of supported time formats organized by category.
        
        Returns:
            Dictionary with categorized examples
        """
        return {
            'flexible_basic': [
                'today',
                'today anytime', 
                'tomorrow',
                'tomorrow anytime',
                'next week',
                'next week anytime',
                'this week',
                'end of week',
                'beginning of week'
            ],
            'weekday_flexible': [
                'monday',
                'next friday anytime',
                'this wednesday',
                'last tuesday',
                'friday sometime'
            ],
            'time_of_day': [
                'this morning',
                'tomorrow afternoon', 
                'tonight',
                'this evening',
                'morning sometime'
            ],
            'relative': [
                'soon',
                'later',
                'later today',
                'sometime this week',
                'sometime next week',
                'in 2 hours',
                '3 days from now'
            ],
            'specific_with_time': [
                'today 3pm',
                'tomorrow 8:30am',
                'friday 7pm',
                'next monday 2pm',
                'january 15 at 8pm'
            ],
            'context_specific': [
                'due by friday',
                'deadline next week', 
                'expires january 15',
                'starts at 8pm tomorrow',
                'scheduled for next week'
            ],
            'standard_formats': [
                '2024-01-15 20:00',
                '1/15/2024 8:00 PM',
                'March 15, 2024',
                '15:30',
                '8:30 PM'
            ]
        }
    
    @staticmethod
    def get_help_text(context: str = "general") -> str:
        """
        Generate helpful text explaining supported formats for a given context.
        
        Args:
            context: Context to generate help for
            
        Returns:
            Formatted help text string
        """
        examples = UniversalTimestamp.get_examples()
        
        help_text = "🕐 **Supported Time Formats:**\n\n"
        
        if context in ["event", "general"]:
            help_text += "📅 **Natural Language:**\n"
            help_text += "• " + ", ".join(examples['flexible_basic'][:4]) + "\n"
            help_text += "• " + ", ".join(examples['weekday_flexible'][:3]) + "\n\n"
            
            help_text += "⏰ **Time of Day:**\n"
            help_text += "• " + ", ".join(examples['time_of_day']) + "\n\n"
            
            help_text += "🎯 **With Specific Times:**\n" 
            help_text += "• " + ", ".join(examples['specific_with_time'][:3]) + "\n\n"
        
        if context == "dues":
            help_text += "💰 **Dues-Specific:**\n"
            help_text += "• " + ", ".join(examples['context_specific'][:3]) + "\n\n"
        
        help_text += "⚡ **Quick Options:**\n"
        help_text += "• " + ", ".join(examples['relative'][:4]) + "\n\n"
        
        help_text += "📋 **Standard Formats:**\n"
        help_text += "• " + ", ".join(examples['standard_formats'][:3]) + "\n\n"
        
        help_text += "✨ **Examples:**\n"
        help_text += "• `tomorrow 8pm` → Tomorrow at 8:00 PM\n"
        help_text += "• `next week anytime` → Next Monday at 12:00 PM\n" 
        help_text += "• `friday afternoon` → This Friday at 2:00 PM\n"
        help_text += "• `due by end of month` → Last day of month at 11:59 PM"
        
        return help_text

class BotTimeUtils:
    """
    Convenience class with common bot-specific timestamp utilities.
    Designed to be easily imported and used throughout the bot.
    """
    
    @staticmethod
    def parse_event_time(time_str: str) -> Optional[datetime]:
        """Parse time specifically for events."""
        return UniversalTimestamp.parse_simple(time_str, "event")
    
    @staticmethod
    def parse_due_date(time_str: str) -> Optional[datetime]:
        """Parse time specifically for dues and deadlines."""
        return UniversalTimestamp.parse_simple(time_str, "dues")
    
    @staticmethod
    def parse_reminder_time(time_str: str) -> Optional[datetime]:
        """Parse time specifically for reminders."""
        return UniversalTimestamp.parse_simple(time_str, "reminder")
    
    @staticmethod
    def format_event_display(dt: datetime) -> str:
        """Format datetime for event display with both absolute and relative times."""
        return UniversalTimestamp.format_flexible(dt, True)
    
    @staticmethod
    def format_due_date_display(dt: datetime) -> str:
        """Format datetime for due date display."""
        formats = UniversalTimestamp.get_all_formats(dt)
        return f"{formats['date_long']} ({formats['relative']})"
    
    @staticmethod
    def quick_parse(time_str: str) -> Optional[datetime]:
        """Quick parsing with automatic context detection."""
        # Try to detect context from the string
        context = "general"
        if any(word in time_str.lower() for word in ['due', 'deadline', 'expires']):
            context = "dues"
        elif any(word in time_str.lower() for word in ['event', 'meeting', 'starts', 'begins']):
            context = "event"
            
        return UniversalTimestamp.parse_simple(time_str, context)
    
    @staticmethod
    def validate_and_parse(time_str: str, context: str = "general") -> tuple[bool, Optional[datetime], str]:
        """
        Validate and parse time string, returning success status, datetime, and error message.
        
        Returns:
            Tuple of (success, datetime, error_message)
        """
        if not time_str or not isinstance(time_str, str):
            return False, None, "No time provided"
        
        result = UniversalTimestamp.parse(time_str, context)
        
        if not result:
            return False, None, f"Could not parse time: '{time_str}'"
        
        if not result.get('is_valid'):
            error_msg = result.get('error', 'Invalid time format')
            return False, None, error_msg
        
        return True, result['datetime'], ""

# Export commonly used functions for easy importing
parse_time = UniversalTimestamp.parse_simple
format_discord = UniversalTimestamp.to_discord
is_valid = UniversalTimestamp.is_valid_time
get_help = UniversalTimestamp.get_help_text

# Export bot utilities
parse_event = BotTimeUtils.parse_event_time
parse_due = BotTimeUtils.parse_due_date
format_event = BotTimeUtils.format_event_display
quick_parse = BotTimeUtils.quick_parse
validate_time = BotTimeUtils.validate_and_parse
