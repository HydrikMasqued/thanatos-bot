#!/usr/bin/env python3
"""
Comprehensive Test Script for Timestamp System
Tests all parsing functionality to ensure 100% reliability
"""

import sys
import os
import traceback
from datetime import datetime, timedelta

# Add the project directory to sys.path to allow imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test all imports work correctly"""
    print("🔍 Testing imports...")
    try:
        from utils.advanced_timestamp_parser import AdvancedTimestampParser
        from utils.smart_time_formatter import SmartTimeFormatter
        from utils.universal_timestamp import (
            UniversalTimestamp, BotTimeUtils,
            parse_time, format_discord, is_valid, get_help,
            parse_event, parse_due, quick_parse, validate_time
        )
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        traceback.print_exc()
        return False

def test_basic_parsing():
    """Test basic timestamp parsing functionality"""
    print("\n🔍 Testing basic parsing...")
    
    from utils.universal_timestamp import parse_time
    
    test_cases = [
        ("today", "Should parse to today"),
        ("tomorrow", "Should parse to tomorrow"),  
        ("next week", "Should parse to next week"),
        ("friday", "Should parse to this friday"),
        ("tomorrow 8pm", "Should parse to tomorrow 8pm"),
        ("next friday 3pm", "Should parse to next friday 3pm"),
        ("2024-01-15 14:30", "Should parse ISO format"),
    ]
    
    all_passed = True
    for test_input, description in test_cases:
        try:
            result = parse_time(test_input)
            if result:
                print(f"✅ {test_input:20} → {result.strftime('%Y-%m-%d %H:%M')} ({description})")
            else:
                print(f"❌ {test_input:20} → Failed to parse ({description})")
                all_passed = False
        except Exception as e:
            print(f"❌ {test_input:20} → Error: {e}")
            all_passed = False
    
    return all_passed

def test_flexible_expressions():
    """Test new flexible time expressions"""
    print("\n🔍 Testing flexible expressions...")
    
    from utils.universal_timestamp import parse_time
    
    flexible_cases = [
        ("today anytime", "Should parse today with default time"),
        ("tomorrow anytime", "Should parse tomorrow with default time"),
        ("next week anytime", "Should parse next week with default time"),
        ("friday anytime", "Should parse friday with default time"),
        ("this morning", "Should parse this morning"),
        ("tomorrow afternoon", "Should parse tomorrow afternoon"),
        ("tonight", "Should parse tonight"),
        ("end of week", "Should parse end of week"),
        ("beginning of week", "Should parse beginning of week"),
        ("soon", "Should parse soon"),
        ("later", "Should parse later"),
        ("sometime this week", "Should parse sometime this week"),
        ("sometime next week", "Should parse sometime next week"),
    ]
    
    all_passed = True
    for test_input, description in flexible_cases:
        try:
            result = parse_time(test_input)
            if result:
                print(f"✅ {test_input:25} → {result.strftime('%Y-%m-%d %H:%M')} ({description})")
            else:
                print(f"❌ {test_input:25} → Failed to parse ({description})")
                all_passed = False
        except Exception as e:
            print(f"❌ {test_input:25} → Error: {e}")
            all_passed = False
    
    return all_passed

def test_context_parsing():
    """Test context-specific parsing"""
    print("\n🔍 Testing context-specific parsing...")
    
    from utils.universal_timestamp import parse_event, parse_due
    
    context_cases = [
        ("starts at 8pm tomorrow", parse_event, "Event context"),
        ("begins on friday", parse_event, "Event context"),
        ("scheduled for next week", parse_event, "Event context"),
        ("due by friday", parse_due, "Dues context"),
        ("deadline next week", parse_due, "Dues context"),
        ("expires january 15", parse_due, "Dues context"),
    ]
    
    all_passed = True
    for test_input, parser_func, description in context_cases:
        try:
            result = parser_func(test_input)
            if result:
                print(f"✅ {test_input:25} → {result.strftime('%Y-%m-%d %H:%M')} ({description})")
            else:
                print(f"❌ {test_input:25} → Failed to parse ({description})")
                all_passed = False
        except Exception as e:
            print(f"❌ {test_input:25} → Error: {e}")
            all_passed = False
    
    return all_passed

def test_validation():
    """Test validation functionality"""
    print("\n🔍 Testing validation...")
    
    from utils.universal_timestamp import validate_time, is_valid
    
    valid_cases = [
        "tomorrow 8pm",
        "next week anytime", 
        "friday afternoon",
        "today",
        "2024-01-15 14:30"
    ]
    
    invalid_cases = [
        "invalid time string",
        "tomorrow yesterday", 
        "not a time",
        "",
        None
    ]
    
    all_passed = True
    
    # Test valid cases
    print("  Testing valid cases...")
    for test_case in valid_cases:
        try:
            is_valid_result = is_valid(test_case)
            success, dt, error = validate_time(test_case)
            
            if is_valid_result and success and dt:
                print(f"  ✅ {str(test_case):25} → Valid (both methods agree)")
            else:
                print(f"  ❌ {str(test_case):25} → Inconsistent results")
                all_passed = False
        except Exception as e:
            print(f"  ❌ {str(test_case):25} → Error: {e}")
            all_passed = False
    
    # Test invalid cases  
    print("  Testing invalid cases...")
    for test_case in invalid_cases:
        try:
            is_valid_result = is_valid(test_case) if test_case is not None else False
            success, dt, error = validate_time(test_case) if test_case is not None else (False, None, "None input")
            
            if not is_valid_result and not success:
                print(f"  ✅ {str(test_case):25} → Correctly identified as invalid")
            else:
                print(f"  ❌ {str(test_case):25} → Should be invalid but passed")
                all_passed = False
        except Exception as e:
            # Exceptions for invalid input are expected
            print(f"  ✅ {str(test_case):25} → Correctly threw exception")
    
    return all_passed

def test_discord_formatting():
    """Test Discord timestamp formatting"""
    print("\n🔍 Testing Discord formatting...")
    
    from utils.universal_timestamp import format_discord, UniversalTimestamp
    
    try:
        test_dt = datetime(2025, 1, 15, 20, 30, 0)
        
        # Test basic formatting
        formatted = format_discord(test_dt, 'F')
        if formatted.startswith('<t:') and formatted.endswith(':F>'):
            print("✅ Basic Discord formatting works")
        else:
            print(f"❌ Basic formatting failed: {formatted}")
            return False
            
        # Test all format styles
        all_formats = UniversalTimestamp.get_all_formats(test_dt)
        expected_styles = ['full_long', 'full_short', 'date_long', 'date_short', 'time_long', 'time_short', 'relative']
        
        for style in expected_styles:
            if style in all_formats and all_formats[style].startswith('<t:'):
                print(f"✅ {style:12} format: {all_formats[style]}")
            else:
                print(f"❌ {style:12} format failed")
                return False
                
        return True
        
    except Exception as e:
        print(f"❌ Discord formatting error: {e}")
        return False

def test_error_handling():
    """Test error handling and edge cases"""
    print("\n🔍 Testing error handling...")
    
    from utils.universal_timestamp import UniversalTimestamp
    
    edge_cases = [
        None,
        "",
        " ",
        "not a time at all",
        "tomorrow yesterday",  # Contradictory
        "32nd of january",  # Invalid date
        "25:99",  # Invalid time
        "random text with no time meaning",
        123,  # Non-string input
        [],  # Wrong type
    ]
    
    all_passed = True
    for test_case in edge_cases:
        try:
            result = UniversalTimestamp.parse(str(test_case) if test_case is not None else test_case)
            
            if result is None or (result and not result.get('is_valid')):
                print(f"✅ {str(test_case):30} → Correctly handled as invalid")
            else:
                print(f"❌ {str(test_case):30} → Should have failed but didn't")
                all_passed = False
                
        except Exception as e:
            # Exceptions are acceptable for invalid input
            print(f"✅ {str(test_case):30} → Exception handled: {type(e).__name__}")
    
    return all_passed

def test_integration_compatibility():
    """Test compatibility with existing systems"""
    print("\n🔍 Testing integration compatibility...")
    
    try:
        # Test SmartTimeFormatter integration
        from utils.smart_time_formatter import SmartTimeFormatter
        from utils.advanced_timestamp_parser import AdvancedTimestampParser
        
        # Test that SmartTimeFormatter methods still work
        test_dt = datetime(2025, 1, 15, 20, 30, 0)
        discord_ts = SmartTimeFormatter.format_discord_timestamp(test_dt, 'F')
        event_format = SmartTimeFormatter.format_event_datetime(test_dt)
        
        if discord_ts.startswith('<t:') and event_format:
            print("✅ SmartTimeFormatter compatibility maintained")
        else:
            print("❌ SmartTimeFormatter compatibility broken")
            return False
            
        # Test that advanced parser can create results
        result = AdvancedTimestampParser.parse_any_timestamp("tomorrow 8pm")
        if result and result.get('is_valid') and result.get('datetime'):
            print("✅ AdvancedTimestampParser integration works")
        else:
            print("❌ AdvancedTimestampParser integration failed") 
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Integration compatibility error: {e}")
        traceback.print_exc()
        return False

def run_comprehensive_test():
    """Run all tests and return overall result"""
    print("🧪 COMPREHENSIVE TIMESTAMP SYSTEM TEST")
    print("=" * 50)
    
    tests = [
        ("Import Tests", test_imports),
        ("Basic Parsing", test_basic_parsing), 
        ("Flexible Expressions", test_flexible_expressions),
        ("Context Parsing", test_context_parsing),
        ("Validation", test_validation),
        ("Discord Formatting", test_discord_formatting),
        ("Error Handling", test_error_handling),
        ("Integration Compatibility", test_integration_compatibility),
    ]
    
    results = {}
    all_passed = True
    
    for test_name, test_func in tests:
        print(f"\n{test_name}")
        print("-" * len(test_name))
        try:
            result = test_func()
            results[test_name] = result
            if not result:
                all_passed = False
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            traceback.print_exc()
            results[test_name] = False
            all_passed = False
    
    # Summary
    print("\n" + "=" * 50)
    print("🎯 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:25} {status}")
    
    print("-" * 50)
    if all_passed:
        print("🎉 ALL TESTS PASSED - SYSTEM IS 100% FUNCTIONAL!")
        print("✅ Ready for deployment")
    else:
        print("⚠️  SOME TESTS FAILED - ISSUES NEED FIXING")
        print("❌ Review failed tests before deployment")
    
    print("=" * 50)
    return all_passed

if __name__ == "__main__":
    success = run_comprehensive_test()
    sys.exit(0 if success else 1)
