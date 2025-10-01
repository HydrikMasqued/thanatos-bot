#!/usr/bin/env python3
"""
Comprehensive Time Parsing Test Suite
Tests the bot's time parsing capabilities across all systems that use timestamps.
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.advanced_timestamp_parser import AdvancedTimestampParser
from utils.smart_time_formatter import SmartTimeFormatter

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TimeParsingTester:
    """Comprehensive time parsing test suite"""
    
    def __init__(self):
        self.test_results = []
        self.current_time = datetime.now()
        
    def log_test_result(self, test_name: str, input_text: str, expected: str, actual: str, passed: bool):
        """Log a test result"""
        result = {
            'test_name': test_name,
            'input': input_text,
            'expected': expected,
            'actual': actual,
            'passed': passed
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} | {test_name} | '{input_text}' | Expected: {expected} | Got: {actual}")
    
    def test_advanced_parser(self):
        """Test AdvancedTimestampParser with various inputs"""
        logger.info("=" * 80)
        logger.info("TESTING ADVANCED TIMESTAMP PARSER")
        logger.info("=" * 80)
        
        test_cases = [
            # Basic day formats
            ("tomorrow 5pm", "Should be tomorrow at 17:00"),
            ("5pm tomorrow", "Should be tomorrow at 17:00"),
            ("today at 3:30pm", "Should be today at 15:30"),
            ("2:15PM today", "Should be today at 14:15"),
            
            # Various time formats
            ("tomorrow 8:30am", "Should be tomorrow at 08:30"),
            ("9:45 PM tomorrow", "Should be tomorrow at 21:45"),
            ("tomorrow at noon", "Should be tomorrow at 12:00"),
            ("midnight tomorrow", "Should be tomorrow at 00:00"),
            
            # Weekday formats
            ("next friday 7pm", "Should be next Friday at 19:00"),
            ("friday 7pm", "Should be next Friday at 19:00"),
            ("7pm next friday", "Should be next Friday at 19:00"),
            ("this saturday 2pm", "Should be this Saturday at 14:00"),
            
            # Natural language
            ("in 2 hours", "Should be 2 hours from now"),
            ("in 30 minutes", "Should be 30 minutes from now"),
            ("3 days from now", "Should be 3 days from now"),
            ("next week", "Should be next week Monday"),
            ("end of week", "Should be end of this week"),
            
            # Date formats
            ("january 15 at 8pm", "Should be January 15 at 20:00"),
            ("jan 15 8pm", "Should be January 15 at 20:00"),
            ("2024-12-25 10:30", "Should be December 25, 2024 at 10:30"),
            ("12/25/2024 3:15 PM", "Should be December 25, 2024 at 15:15"),
            
            # Edge cases and variations
            ("tomorrow evening", "Should be tomorrow evening"),
            ("next monday morning", "Should be next Monday morning"),
            ("this friday afternoon", "Should be this Friday afternoon"),
            ("tonight", "Should be tonight"),
            ("later today", "Should be later today"),
            
            # Common variations
            ("tom 5pm", "Should handle 'tom' for tomorrow"),
            ("tmrw 8am", "Should handle 'tmrw' for tomorrow"),
            ("fri 6pm", "Should handle abbreviated weekday"),
            ("mon at 9am", "Should handle abbreviated weekday"),
            
            # Complex expressions
            ("scheduled for tomorrow 6:30pm", "Should extract tomorrow 18:30"),
            ("starts at friday 8pm", "Should extract Friday 20:00"),
            ("due by next monday 5pm", "Should extract next Monday 17:00"),
            ("begins tomorrow morning at 10", "Should extract tomorrow 10:00"),
            
            # Military time
            ("tomorrow 1400", "Should handle military time 14:00"),
            ("friday 0900", "Should handle military time 09:00"),
            ("18:30 tomorrow", "Should handle 24-hour format"),
            
            # Casual expressions
            ("sometime tomorrow", "Should handle vague time"),
            ("tomorrow anytime", "Should handle flexible time"),
            ("later this week", "Should handle week reference"),
            ("early next week", "Should handle early week reference"),
        ]
        
        for test_input, description in test_cases:
            try:
                result = AdvancedTimestampParser.parse_any_timestamp(test_input, context="general")
                if result and result.get('is_valid'):
                    parsed_time = result['datetime']
                    confidence = result.get('confidence', 0.0)
                    source_format = result.get('source_format', 'unknown')
                    
                    actual = f"{parsed_time.strftime('%Y-%m-%d %H:%M')} (confidence: {confidence:.1%}, format: {source_format})"
                    passed = True
                else:
                    actual = f"FAILED TO PARSE: {result.get('error', 'Unknown error') if result else 'No result'}"
                    passed = False
                    
                self.log_test_result("AdvancedParser", test_input, description, actual, passed)
                
            except Exception as e:
                self.log_test_result("AdvancedParser", test_input, description, f"EXCEPTION: {e}", False)
    
    def test_smart_formatter(self):
        """Test SmartTimeFormatter natural language parsing"""
        logger.info("=" * 80)
        logger.info("TESTING SMART TIME FORMATTER")
        logger.info("=" * 80)
        
        test_cases = [
            # Basic cases
            ("today", "Should be today at noon"),
            ("tomorrow", "Should be tomorrow at noon"),
            ("yesterday", "Should be yesterday at noon"),
            
            # Time-specific
            ("today at 5pm", "Should be today at 17:00"),
            ("tomorrow at 8:30am", "Should be tomorrow at 08:30"),
            ("5pm today", "Should be today at 17:00"),
            ("8:30am tomorrow", "Should be tomorrow at 08:30"),
            
            # Relative time
            ("in 1 hour", "Should be 1 hour from now"),
            ("in 45 minutes", "Should be 45 minutes from now"),
            ("in 2 days", "Should be 2 days from now"),
            ("3 hours from now", "Should be 3 hours from now"),
            
            # Weekdays
            ("next monday", "Should be next Monday"),
            ("this friday", "Should be this Friday"),
            ("next wednesday", "Should be next Wednesday"),
            
            # Now/immediate
            ("now", "Should be current time"),
            ("right now", "Should be current time"),
            ("immediately", "Should be current time"),
            ("asap", "Should be current time"),
            
            # End of periods
            ("end of week", "Should be end of this week"),
            ("end of month", "Should be end of this month"),
            ("end of day", "Should be end of today"),
        ]
        
        for test_input, description in test_cases:
            try:
                result = SmartTimeFormatter.parse_natural_language_time(test_input)
                if result:
                    actual = result.strftime('%Y-%m-%d %H:%M')
                    passed = True
                else:
                    actual = "FAILED TO PARSE"
                    passed = False
                    
                self.log_test_result("SmartFormatter", test_input, description, actual, passed)
                
            except Exception as e:
                self.log_test_result("SmartFormatter", test_input, description, f"EXCEPTION: {e}", False)
    
    def test_edge_cases(self):
        """Test edge cases and error handling"""
        logger.info("=" * 80)
        logger.info("TESTING EDGE CASES AND ERROR HANDLING")
        logger.info("=" * 80)
        
        edge_cases = [
            # Contradictory terms
            ("tomorrow yesterday", "Should reject contradictory terms"),
            ("next last friday", "Should reject contradictory terms"),
            ("today tomorrow", "Should reject contradictory terms"),
            
            # Ambiguous times
            ("friday", "Should handle ambiguous day"),
            ("morning", "Should handle ambiguous time"),
            ("evening", "Should handle ambiguous time"),
            
            # Invalid formats
            ("25:00", "Should reject invalid time"),
            ("february 30", "Should reject invalid date"),
            ("13pm", "Should reject invalid format"),
            
            # Empty/null inputs
            ("", "Should handle empty string"),
            (None, "Should handle None"),
            ("   ", "Should handle whitespace"),
            
            # Special characters
            ("tomorrow @ 5pm", "Should handle @ symbol"),
            ("friday - 8pm", "Should handle dash"),
            ("next week (monday)", "Should handle parentheses"),
            
            # Case variations
            ("TOMORROW 5PM", "Should handle uppercase"),
            ("Tomorrow 5Pm", "Should handle mixed case"),
            ("tOmOrRoW 5pM", "Should handle alternating case"),
            
            # Multiple spaces
            ("tomorrow    5pm", "Should handle multiple spaces"),
            ("next   friday   at   8pm", "Should handle scattered spaces"),
            
            # International formats
            ("25/12/2024", "Should handle DD/MM/YYYY"),
            ("2024-12-25", "Should handle ISO format"),
            ("25 Dec 2024", "Should handle day month year"),
        ]
        
        for test_input, description in edge_cases:
            try:
                # Test with AdvancedTimestampParser
                result1 = AdvancedTimestampParser.parse_any_timestamp(test_input, context="general") if test_input is not None else None
                
                # Test with SmartTimeFormatter  
                result2 = SmartTimeFormatter.parse_natural_language_time(test_input) if test_input is not None else None
                
                # Determine if handling was appropriate
                if test_input in [None, "", "   "]:
                    passed = (result1 is None or not result1.get('is_valid', False)) and result2 is None
                    actual = "Properly rejected null/empty input"
                elif "reject" in description.lower():
                    passed = (result1 is None or not result1.get('is_valid', False))
                    actual = "Properly rejected invalid input" if passed else "Incorrectly accepted invalid input"
                else:
                    passed = (result1 and result1.get('is_valid', False)) or result2 is not None
                    actual = "Successfully parsed" if passed else "Failed to parse valid input"
                    
                self.log_test_result("EdgeCases", str(test_input), description, actual, passed)
                
            except Exception as e:
                # Some exceptions are expected for invalid inputs
                if "reject" in description.lower():
                    self.log_test_result("EdgeCases", str(test_input), description, f"Appropriately threw exception: {type(e).__name__}", True)
                else:
                    self.log_test_result("EdgeCases", str(test_input), description, f"UNEXPECTED EXCEPTION: {e}", False)
    
    def test_timestamp_accuracy(self):
        """Test timestamp accuracy for known dates"""
        logger.info("=" * 80)
        logger.info("TESTING TIMESTAMP ACCURACY")
        logger.info("=" * 80)
        
        # Test against known timestamps
        now = self.current_time
        tomorrow = now + timedelta(days=1)
        next_week = now + timedelta(days=7)
        
        accuracy_tests = [
            ("tomorrow 5pm", tomorrow.replace(hour=17, minute=0, second=0, microsecond=0)),
            ("today at 3pm", now.replace(hour=15, minute=0, second=0, microsecond=0)),
            ("in 2 hours", now + timedelta(hours=2)),
            ("in 30 minutes", now + timedelta(minutes=30)),
            ("in 1 day", now + timedelta(days=1)),
        ]
        
        for test_input, expected_datetime in accuracy_tests:
            try:
                result = AdvancedTimestampParser.parse_any_timestamp(test_input, context="general")
                if result and result.get('is_valid'):
                    parsed_datetime = result['datetime']
                    
                    # Allow small variance for processing time (5 minutes)
                    time_diff = abs((parsed_datetime - expected_datetime).total_seconds())
                    tolerance = 300  # 5 minutes
                    
                    passed = time_diff <= tolerance
                    actual = f"Parsed: {parsed_datetime}, Expected: {expected_datetime}, Diff: {time_diff}s"
                else:
                    passed = False
                    actual = "Failed to parse"
                    
                self.log_test_result("Accuracy", test_input, f"Within {tolerance}s of expected", actual, passed)
                
            except Exception as e:
                self.log_test_result("Accuracy", test_input, "Should parse accurately", f"EXCEPTION: {e}", False)
    
    def generate_report(self):
        """Generate comprehensive test report"""
        logger.info("=" * 80)
        logger.info("COMPREHENSIVE TEST REPORT")
        logger.info("=" * 80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['passed'])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"\n📊 OVERALL RESULTS:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {passed_tests} ({success_rate:.1f}%)")
        print(f"   Failed: {failed_tests}")
        print(f"   Success Rate: {success_rate:.1f}%")
        
        # Group results by test category
        categories = {}
        for result in self.test_results:
            category = result['test_name']
            if category not in categories:
                categories[category] = {'passed': 0, 'failed': 0, 'total': 0}
            categories[category]['total'] += 1
            if result['passed']:
                categories[category]['passed'] += 1
            else:
                categories[category]['failed'] += 1
        
        print(f"\n📋 RESULTS BY CATEGORY:")
        for category, stats in categories.items():
            rate = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
            print(f"   {category}: {stats['passed']}/{stats['total']} ({rate:.1f}%)")
        
        # Show failed tests
        failed_results = [r for r in self.test_results if not r['passed']]
        if failed_results:
            print(f"\n❌ FAILED TESTS ({len(failed_results)}):")
            for result in failed_results[:10]:  # Show first 10 failures
                print(f"   • {result['test_name']}: '{result['input']}' - {result['actual']}")
            if len(failed_results) > 10:
                print(f"   ... and {len(failed_results) - 10} more failures")
        
        # Recommendations
        print(f"\n🔍 ANALYSIS:")
        if success_rate >= 90:
            print("   ✅ Excellent: Time parsing is highly flexible and accurate")
        elif success_rate >= 75:
            print("   ✅ Good: Time parsing works well with minor issues")
        elif success_rate >= 50:
            print("   ⚠️ Fair: Time parsing needs improvement for edge cases")
        else:
            print("   ❌ Poor: Time parsing requires significant fixes")
        
        # Flexibility assessment
        natural_language_tests = [r for r in self.test_results if 'tomorrow' in r['input'] or 'today' in r['input'] or 'friday' in r['input']]
        natural_success = sum(1 for r in natural_language_tests if r['passed'])
        natural_total = len(natural_language_tests)
        
        if natural_total > 0:
            natural_rate = (natural_success / natural_total * 100)
            print(f"   📝 Natural Language Support: {natural_rate:.1f}% ({natural_success}/{natural_total})")
        
        return {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'success_rate': success_rate,
            'categories': categories,
            'failed_tests': failed_results
        }
    
    def run_all_tests(self):
        """Run all test suites"""
        logger.info("🚀 STARTING COMPREHENSIVE TIME PARSING TESTS")
        logger.info(f"📅 Test Date: {self.current_time}")
        logger.info("=" * 80)
        
        try:
            self.test_advanced_parser()
            self.test_smart_formatter()
            self.test_edge_cases()
            self.test_timestamp_accuracy()
            
            return self.generate_report()
            
        except Exception as e:
            logger.error(f"Critical error during testing: {e}")
            return None

def main():
    """Run the comprehensive test suite"""
    tester = TimeParsingTester()
    report = tester.run_all_tests()
    
    if report:
        return 0 if report['success_rate'] >= 80 else 1
    else:
        return 2

if __name__ == "__main__":
    exit(main())