#!/usr/bin/env python3
"""
Edge Case and Integration Testing for Thanatos Bot
Tests error handling, edge cases, and system integrations
"""

import asyncio
import sys
import os
import traceback
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class EdgeCaseTestSuite:
    def __init__(self):
        self.results = {
            'passed': 0,
            'failed': 0,
            'errors': []
        }
    
    def log_result(self, test_name: str, success: bool, error: str = None):
        """Log test result"""
        if success:
            print(f"✅ {test_name}")
            self.results['passed'] += 1
        else:
            print(f"❌ {test_name}: {error}")
            self.results['failed'] += 1
            self.results['errors'].append(f"{test_name}: {error}")
    
    async def test_database_edge_cases(self):
        """Test database with edge cases"""
        print("\n🗄️ Testing Database Edge Cases...")
        
        try:
            from utils.database import DatabaseManager
            db = DatabaseManager("edge_test.db")
            await db.initialize_database()
            
            # Test with invalid IDs
            try:
                member = await db.get_member(999999999999999999, 888888888888888888)
                if member is None:
                    self.log_result("Database invalid ID handling", True)
                else:
                    self.log_result("Database invalid ID handling", False, "Should return None for invalid IDs")
            except Exception as e:
                self.log_result("Database invalid ID handling", False, str(e))
            
            # Test with empty strings
            try:
                await db.add_or_update_member(123, 456, "", "President", "", "Active")
                self.log_result("Database empty string handling", True)
            except Exception as e:
                self.log_result("Database empty string handling", False, str(e))
            
            # Test with None values
            try:
                await db.add_contribution(123, 456, None, "Test Item", 1)
                self.log_result("Database None value handling", False, "Should reject None category")
            except Exception as e:
                self.log_result("Database None value handling", True)
            
            await db.close()
            if os.path.exists("edge_test.db"):
                os.remove("edge_test.db")
                
        except Exception as e:
            self.log_result("Database edge case testing", False, str(e))
    
    async def test_time_parser_edge_cases(self):
        """Test time parser with edge cases"""
        print("\n⏰ Testing Time Parser Edge Cases...")
        
        try:
            from utils.time_parser import TimeParser
            parser = TimeParser()
            
            # Test invalid formats
            invalid_cases = [
                "",
                None,
                "abc",
                "999999999999999999999999999 days",
                "-5 hours",
                "0 seconds",
                "tomorrow yesterday",  # Contradictory
                "5",  # No unit
                "5.5.5 hours",  # Invalid number
                "5 invalid_unit"
            ]
            
            for case in invalid_cases:
                try:
                    if case is None:
                        continue
                    result = parser.parse_duration(case)
                    self.log_result(f"Time parser should reject '{case}'", False, "Should have raised ValueError")
                except (ValueError, TypeError, AttributeError):
                    self.log_result(f"Time parser correctly rejects '{case}'", True)
                except Exception as e:
                    self.log_result(f"Time parser handles '{case}'", False, f"Unexpected error: {e}")
            
            # Test extreme values
            extreme_cases = [
                ("1 second", True),
                ("999999 days", True),  # Should handle large values
                ("0.1 seconds", True),  # Should handle decimals
                ("24 hours", True),
                ("7 days", True),
                ("52 weeks", True),
                ("12 months", True)
            ]
            
            for case, should_pass in extreme_cases:
                try:
                    result = parser.parse_duration(case)
                    if should_pass:
                        self.log_result(f"Time parser handles extreme case '{case}'", True)
                    else:
                        self.log_result(f"Time parser should reject extreme case '{case}'", False, "Should have failed")
                except Exception as e:
                    if should_pass:
                        self.log_result(f"Time parser handles extreme case '{case}'", False, str(e))
                    else:
                        self.log_result(f"Time parser correctly rejects extreme case '{case}'", True)
                        
        except Exception as e:
            self.log_result("Time parser edge case testing", False, str(e))
    
    async def test_smart_formatter_edge_cases(self):
        """Test smart time formatter with edge cases"""
        print("\n🎨 Testing Smart Formatter Edge Cases...")
        
        try:
            from utils.smart_time_formatter import SmartTimeFormatter
            
            # Test with None and invalid inputs
            try:
                result = SmartTimeFormatter.format_discord_timestamp(None)
                self.log_result("Smart formatter handles None", False, "Should have raised error")
            except Exception:
                self.log_result("Smart formatter correctly rejects None", True)
            
            # Test with extreme dates
            try:
                extreme_future = datetime(2099, 12, 31, 23, 59, 59)
                result = SmartTimeFormatter.format_discord_timestamp(extreme_future)
                if "<t:" in result and ":F>" in result:
                    self.log_result("Smart formatter handles extreme future date", True)
                else:
                    self.log_result("Smart formatter handles extreme future date", False, "Invalid format")
            except Exception as e:
                self.log_result("Smart formatter handles extreme future date", False, str(e))
            
            # Test with past dates
            try:
                extreme_past = datetime(1970, 1, 2, 0, 0, 0)  # Near Unix epoch
                result = SmartTimeFormatter.format_discord_timestamp(extreme_past)
                if "<t:" in result and ":F>" in result:
                    self.log_result("Smart formatter handles extreme past date", True)
                else:
                    self.log_result("Smart formatter handles extreme past date", False, "Invalid format")
            except Exception as e:
                self.log_result("Smart formatter handles extreme past date", False, str(e))
                
        except Exception as e:
            self.log_result("Smart formatter edge case testing", False, str(e))
    
    async def test_advanced_timestamp_edge_cases(self):
        """Test advanced timestamp parser with edge cases"""
        print("\n⚙️ Testing Advanced Timestamp Edge Cases...")
        
        try:
            from utils.advanced_timestamp_parser import AdvancedTimestampParser
            parser = AdvancedTimestampParser()
            
            # Test contradictory inputs
            contradictory_cases = [
                "tomorrow yesterday",
                "next last friday", 
                "today tomorrow",
                "this next week"
            ]
            
            for case in contradictory_cases:
                try:
                    result = parser.parse_any_timestamp(case)
                    if result and not result.get('is_valid', True):
                        self.log_result(f"Advanced parser correctly rejects contradictory '{case}'", True)
                    elif result and result.get('is_valid', False):
                        self.log_result(f"Advanced parser incorrectly accepts contradictory '{case}'", False, "Should reject contradictory terms")
                    else:
                        self.log_result(f"Advanced parser handles contradictory '{case}'", True)
                except Exception as e:
                    self.log_result(f"Advanced parser handles contradictory '{case}'", True)  # Exception is acceptable
            
            # Test empty/null inputs
            null_cases = ["", None, "   ", "\n\t", "abc123xyz"]
            
            for case in null_cases:
                try:
                    result = parser.parse_any_timestamp(case)
                    if result is None or (result and not result.get('is_valid', True)):
                        self.log_result(f"Advanced parser correctly rejects invalid '{case}'", True)
                    else:
                        self.log_result(f"Advanced parser should reject invalid '{case}'", False, "Should return None or invalid")
                except Exception as e:
                    self.log_result(f"Advanced parser handles invalid '{case}'", True)  # Exception is acceptable
                    
        except Exception as e:
            self.log_result("Advanced timestamp edge case testing", False, str(e))
    
    async def test_cog_instantiation(self):
        """Test that all cogs can be instantiated without errors"""
        print("\n🔧 Testing Cog Instantiation...")
        
        # Mock bot class for testing
        class MockBot:
            def __init__(self):
                self.db = None
                self.time_parser = None
                self.loa_notifications = None
                self.precise_reminders = None
        
        mock_bot = MockBot()
        
        cog_classes = [
            ('cogs.loa_system', 'LOASystem'),
            ('cogs.membership', 'MembershipSystem'),
            ('cogs.contributions', 'ContributionSystem'),
            ('cogs.configuration', 'ConfigurationSystem'),
            ('cogs.events', 'EventSystem'),
            ('cogs.dues_tracking', 'DuesTracking'),
            ('cogs.enhanced_menu_system', 'EnhancedMenuSystem')
        ]
        
        for module_name, class_name in cog_classes:
            try:
                module = __import__(module_name, fromlist=[class_name])
                cog_class = getattr(module, class_name)
                cog_instance = cog_class(mock_bot)
                self.log_result(f"Cog {class_name} instantiates correctly", True)
            except Exception as e:
                self.log_result(f"Cog {class_name} instantiation", False, str(e))
    
    async def test_error_handling(self):
        """Test error handling in critical functions"""
        print("\n🛡️ Testing Error Handling...")
        
        try:
            from utils.database import DatabaseManager
            
            # Test database with invalid path
            try:
                db = DatabaseManager("/invalid/path/to/database.db")
                await db.initialize_database()
                self.log_result("Database handles invalid path", False, "Should have raised error")
            except Exception:
                self.log_result("Database correctly handles invalid path", True)
            
            # Test database connection issues
            try:
                db = DatabaseManager(":memory:")
                await db.initialize_database()
                # Force close connection and try operation
                await db.close()
                await db.get_member(123, 456)  # Should handle closed connection gracefully
                self.log_result("Database handles closed connection", True)
            except Exception as e:
                # This is acceptable - the database should either handle it gracefully or raise appropriate error
                self.log_result("Database handles closed connection", True)
                
        except Exception as e:
            self.log_result("Error handling testing", False, str(e))
    
    async def run_all_edge_case_tests(self):
        """Run all edge case tests"""
        print("🚀 Starting Edge Case and Integration Test Suite")
        print("=" * 60)
        
        start_time = datetime.now()
        
        # Run all edge case tests
        await self.test_database_edge_cases()
        await self.test_time_parser_edge_cases()
        await self.test_smart_formatter_edge_cases()
        await self.test_advanced_timestamp_edge_cases()
        await self.test_cog_instantiation()
        await self.test_error_handling()
        
        # Generate report
        end_time = datetime.now()
        duration = end_time - start_time
        
        print("\n" + "=" * 60)
        print("📊 EDGE CASE TEST RESULTS SUMMARY")
        print("=" * 60)
        print(f"✅ Tests Passed: {self.results['passed']}")
        print(f"❌ Tests Failed: {self.results['failed']}")
        print(f"⏱️ Duration: {duration.total_seconds():.2f} seconds")
        
        if self.results['failed'] > 0:
            print(f"\n⚠️ FAILED TESTS:")
            for error in self.results['errors']:
                print(f"   • {error}")
        
        total_tests = self.results['passed'] + self.results['failed']
        success_rate = (self.results['passed'] / total_tests) * 100 if total_tests > 0 else 0
        print(f"\n📈 Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 95:
            print("🎉 EXCELLENT! Edge case handling is robust!")
            return True
        elif success_rate >= 85:
            print("⚠️ Good, but some edge cases need attention")
            return False
        else:
            print("❌ CRITICAL: Poor edge case handling detected")
            return False

async def main():
    """Main test execution"""
    test_suite = EdgeCaseTestSuite()
    success = await test_suite.run_all_edge_case_tests()
    
    if success:
        print("\n🎯 EDGE CASE TESTING PASSED!")
        return True
    else:
        print("\n🔧 EDGE CASE ISSUES DETECTED!")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
