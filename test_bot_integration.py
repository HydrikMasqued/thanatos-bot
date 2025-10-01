#!/usr/bin/env python3
"""
Bot Integration Test - Tests time parsing in actual bot commands
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.advanced_timestamp_parser import AdvancedTimestampParser

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_event_creation_scenarios():
    """Test time parsing scenarios for event creation commands"""
    logger.info("=" * 80)
    logger.info("TESTING EVENT CREATION TIME PARSING")
    logger.info("=" * 80)
    
    event_scenarios = [
        # User-friendly formats
        "tomorrow 7PM",
        "7PM tomorrow", 
        "friday at 8pm",
        "next monday 6:30pm",
        "today at 5:30pm",
        "this weekend 2pm",
        "next week 7pm",
        "january 15 at 8pm",
        "in 3 hours",
        "tomorrow evening",
        "friday night",
        
        # Complex real-world inputs
        "scheduled for tomorrow 6:30pm",
        "starts friday 8pm",
        "next tuesday morning at 10",
        "due by monday 5pm",
        "sometime next week",
        "later this week",
    ]
    
    passed = 0
    total = len(event_scenarios)
    
    for scenario in event_scenarios:
        try:
            result = AdvancedTimestampParser.parse_any_timestamp(scenario, context="event")
            if result and result.get('is_valid'):
                parsed_time = result['datetime']
                confidence = result.get('confidence', 0.0)
                
                # Verify the parsed time is in the future
                if parsed_time > datetime.now():
                    status = "✅ PASS"
                    passed += 1
                else:
                    status = "⚠️ WARN (Past time)"
                    
                logger.info(f"{status} | '{scenario}' -> {parsed_time.strftime('%Y-%m-%d %H:%M')} (confidence: {confidence:.1%})")
            else:
                logger.info(f"❌ FAIL | '{scenario}' -> Failed to parse")
        except Exception as e:
            logger.info(f"❌ ERROR | '{scenario}' -> Exception: {e}")
    
    success_rate = (passed / total * 100)
    logger.info(f"\nEvent Creation Tests: {passed}/{total} ({success_rate:.1f}%)")
    return success_rate

def test_dues_system_scenarios():
    """Test time parsing scenarios for dues system"""
    logger.info("=" * 80)
    logger.info("TESTING DUES SYSTEM TIME PARSING")
    logger.info("=" * 80)
    
    dues_scenarios = [
        # Common due date formats
        "next friday",
        "end of month",
        "january 31",
        "15th of next month",
        "next monday 5pm",
        "friday at 11:59pm",
        "december 1st",
        "in 2 weeks",
        "end of week",
        "tomorrow",
        
        # Complex scenarios
        "due by friday 5pm",
        "deadline next monday",
        "expires end of month",
        "payment due friday",
    ]
    
    passed = 0
    total = len(dues_scenarios)
    
    for scenario in dues_scenarios:
        try:
            result = AdvancedTimestampParser.parse_any_timestamp(scenario, context="dues")
            if result and result.get('is_valid'):
                parsed_time = result['datetime']
                confidence = result.get('confidence', 0.0)
                
                status = "✅ PASS"
                passed += 1
                    
                logger.info(f"{status} | '{scenario}' -> {parsed_time.strftime('%Y-%m-%d %H:%M')} (confidence: {confidence:.1%})")
            else:
                logger.info(f"❌ FAIL | '{scenario}' -> Failed to parse")
        except Exception as e:
            logger.info(f"❌ ERROR | '{scenario}' -> Exception: {e}")
    
    success_rate = (passed / total * 100)
    logger.info(f"\nDues System Tests: {passed}/{total} ({success_rate:.1f}%)")
    return success_rate

def test_time_converter_scenarios():
    """Test time parsing scenarios for /time command"""
    logger.info("=" * 80)
    logger.info("TESTING /TIME COMMAND SCENARIOS")
    logger.info("=" * 80)
    
    time_scenarios = [
        # Various user inputs for time conversion
        "5PM tomorrow",
        "tomorrow 5PM", 
        "next friday 7:30pm",
        "in 2 hours",
        "today at 3pm",
        "monday at 9am",
        "january 1st 12am",
        "new years eve 11:59pm",
        "christmas day 2pm",
        "next week tuesday",
        "end of month",
        "midnight tonight",
        "noon tomorrow",
        "this weekend",
        
        # Edge cases users might try
        "right now",
        "in a few minutes",
        "later today",
        "sometime tomorrow",
        "early next week",
    ]
    
    passed = 0
    total = len(time_scenarios)
    
    for scenario in time_scenarios:
        try:
            result = AdvancedTimestampParser.parse_any_timestamp(scenario, context="general")
            if result and result.get('is_valid'):
                parsed_time = result['datetime']
                confidence = result.get('confidence', 0.0)
                discord_timestamp = f"<t:{int(parsed_time.timestamp())}:F>"
                
                status = "✅ PASS"
                passed += 1
                    
                logger.info(f"{status} | '{scenario}' -> {discord_timestamp} (confidence: {confidence:.1%})")
            else:
                logger.info(f"❌ FAIL | '{scenario}' -> Failed to parse")
        except Exception as e:
            logger.info(f"❌ ERROR | '{scenario}' -> Exception: {e}")
    
    success_rate = (passed / total * 100)
    logger.info(f"\nTime Converter Tests: {passed}/{total} ({success_rate:.1f}%)")
    return success_rate

def main():
    """Run integration tests"""
    logger.info("🚀 STARTING BOT INTEGRATION TESTS")
    logger.info(f"📅 Test Date: {datetime.now()}")
    
    try:
        event_rate = test_event_creation_scenarios()
        dues_rate = test_dues_system_scenarios()
        time_rate = test_time_converter_scenarios()
        
        overall_rate = (event_rate + dues_rate + time_rate) / 3
        
        logger.info("=" * 80)
        logger.info("INTEGRATION TEST SUMMARY")
        logger.info("=" * 80)
        print(f"\n📊 INTEGRATION TEST RESULTS:")
        print(f"   Event Creation: {event_rate:.1f}%")
        print(f"   Dues System: {dues_rate:.1f}%")
        print(f"   Time Converter: {time_rate:.1f}%")
        print(f"   Overall: {overall_rate:.1f}%")
        
        if overall_rate >= 90:
            print("   ✅ Excellent: Bot commands handle time parsing very well")
        elif overall_rate >= 80:
            print("   ✅ Good: Bot commands handle time parsing well")
        elif overall_rate >= 70:
            print("   ⚠️ Fair: Bot commands need some time parsing improvements")
        else:
            print("   ❌ Poor: Bot commands have significant time parsing issues")
        
        return 0 if overall_rate >= 80 else 1
        
    except Exception as e:
        logger.error(f"Critical error during integration testing: {e}")
        return 2

if __name__ == "__main__":
    exit(main())