#!/usr/bin/env python3
"""
Test script for natural language date/time parsing
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.time_parser import TimeParser

def test_natural_date_parsing():
    """Test various natural language date/time expressions"""
    parser = TimeParser()
    
    test_cases = [
        # Today/Tonight/Tomorrow
        "today 8pm",
        "tonight", 
        "today at 3:30pm",
        "tomorrow 7pm",
        "tomorrow at 2:30",
        
        # Day names
        "friday 8pm",
        "next monday 3pm", 
        "saturday at noon",
        "this thursday 7:30pm",
        
        # Specific dates
        "jan 15 8pm",
        "march 3rd 7:30pm",
        "12/25 6pm",
        "december 31st 11:59pm",
        
        # Relative times
        "in 2 hours",
        "in 30 minutes",
        "in 1 day",
        
        # Time only (should apply to today)
        "8pm",
        "3:30pm",
        "noon",
        "midnight",
        
        # Traditional formats
        "2024-12-25",
        "12/25/2024 14:30",
        "2024-01-15 20:00",
        
        # Special words
        "morning",
        "afternoon", 
        "evening",
        "night"
    ]
    
    print("🧪 Testing Natural Language Date/Time Parsing")
    print("=" * 60)
    
    success_count = 0
    total_count = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        try:
            result = parser.parse_natural_datetime(test_case)
            if result:
                formatted = parser.format_natural_datetime(result)
                print(f"{i:2}. ✅ '{test_case}' -> {formatted}")
                print(f"     📅 {result.strftime('%Y-%m-%d %H:%M:%S')}")
                success_count += 1
            else:
                print(f"{i:2}. ❌ '{test_case}' -> Failed to parse")
        except Exception as e:
            print(f"{i:2}. ❌ '{test_case}' -> Error: {e}")
        
        print()  # Empty line for readability
    
    print("=" * 60)
    print(f"📊 Results: {success_count}/{total_count} successful ({success_count/total_count*100:.1f}%)")
    
    if success_count == total_count:
        print("🎉 All natural language parsing tests passed!")
        return True
    else:
        print(f"⚠️  {total_count - success_count} tests failed")
        return False

if __name__ == "__main__":
    success = test_natural_date_parsing()
    sys.exit(0 if success else 1)
