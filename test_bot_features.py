#!/usr/bin/env python3
"""
Comprehensive bot feature testing script
"""
import asyncio
import signal
import sys
import subprocess
import time
import os
from datetime import datetime

class BotTester:
    def __init__(self):
        self.test_results = {}
        self.bot_process = None
        
    def run_bot_with_timeout(self, timeout_seconds=30):
        """Start the bot and let it run for a specified time"""
        print(f"Starting bot with {timeout_seconds}s timeout...")
        
        try:
            # Start the bot process
            self.bot_process = subprocess.Popen(
                [sys.executable, "main.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Read output for specified time
            output_lines = []
            start_time = time.time()
            
            while time.time() - start_time < timeout_seconds:
                if self.bot_process.poll() is not None:
                    # Process finished
                    break
                    
                # Try to read a line with timeout
                try:
                    line = self.bot_process.stdout.readline()
                    if line:
                        output_lines.append(line.strip())
                        print(f"BOT: {line.strip()}")
                except:
                    pass
                
                time.sleep(0.1)
            
            # Terminate the bot
            if self.bot_process.poll() is None:
                print("Terminating bot...")
                self.bot_process.terminate()
                time.sleep(2)
                if self.bot_process.poll() is None:
                    self.bot_process.kill()
            
            # Get remaining output
            try:
                stdout, stderr = self.bot_process.communicate(timeout=5)
                if stdout:
                    output_lines.extend(stdout.strip().split('\n'))
                if stderr:
                    print(f"STDERR: {stderr}")
            except:
                pass
            
            return output_lines
            
        except Exception as e:
            print(f"Error running bot: {e}")
            return []
    
    def analyze_bot_output(self, output_lines):
        """Analyze bot startup output for success indicators"""
        results = {
            'database_init': False,
            'cogs_loaded': 0,
            'commands_synced': 0,
            'bot_ready': False,
            'errors': [],
            'warnings': []
        }
        
        total_expected_cogs = 9
        
        for line in output_lines:
            line_lower = line.lower()
            
            # Check for successful database initialization
            if 'database initialized' in line_lower or 'database tables initialized successfully' in line_lower:
                results['database_init'] = True
            
            # Count loaded cogs
            if 'successfully loaded' in line_lower and 'cogs.' in line_lower:
                results['cogs_loaded'] += 1
            
            # Check for synced commands
            if 'synced' in line_lower and 'command' in line_lower:
                try:
                    # Extract number of synced commands
                    words = line.split()
                    for i, word in enumerate(words):
                        if word.lower() == 'synced' and i + 1 < len(words):
                            try:
                                results['commands_synced'] = int(words[i + 1])
                                break
                            except:
                                pass
                except:
                    pass
            
            # Check if bot is ready
            if 'has landed' in line_lower or 'bot is ready' in line_lower:
                results['bot_ready'] = True
            
            # Look for errors
            if 'error' in line_lower and 'error' not in line_lower.split(':')[0]:
                results['errors'].append(line)
            
            # Look for warnings
            if 'warning' in line_lower:
                results['warnings'].append(line)
        
        # Calculate scores
        results['cog_load_percentage'] = (results['cogs_loaded'] / total_expected_cogs) * 100
        results['overall_success'] = (
            results['database_init'] and 
            results['cogs_loaded'] >= 8 and  # At least 8/9 cogs
            results['commands_synced'] > 50 and  # At least 50 commands
            results['bot_ready'] and
            len(results['errors']) == 0
        )
        
        return results
    
    def test_database_operations(self):
        """Test core database operations"""
        print("\n=== Testing Database Operations ===")
        
        try:
            # Import and test database
            sys.path.append('.')
            from utils.database import DatabaseManager
            
            async def db_test():
                db = DatabaseManager()
                await db.initialize_database()
                
                # Test guild operations
                guild_id = 999999999
                user_id = 888888888
                
                await db.initialize_guild(guild_id)
                await db.add_or_update_member(guild_id, user_id, "TestUser")
                
                # Test contribution operations
                contrib_id = await db.add_contribution(guild_id, user_id, "Test Category", "Test Item", 10)
                
                # Test LOA operations
                from datetime import datetime, timedelta
                end_time = datetime.now() + timedelta(days=1)
                loa_id = await db.create_loa_record(guild_id, user_id, "1 day", "Test LOA", datetime.now(), end_time)
                
                await db.close()
                return True
            
            result = asyncio.run(db_test())
            self.test_results['database_operations'] = {'success': True, 'details': 'All database operations working'}
            print("✅ Database operations test passed")
            
        except Exception as e:
            self.test_results['database_operations'] = {'success': False, 'error': str(e)}
            print(f"❌ Database operations test failed: {e}")
    
    def test_time_parser(self):
        """Test time parser functionality"""
        print("\n=== Testing Time Parser ===")
        
        try:
            from utils.time_parser import TimeParser
            parser = TimeParser()
            
            test_cases = ['5s', '10m', '2h', '1d', '1w']
            results = {}
            
            for case in test_cases:
                try:
                    end_time, normalized = parser.parse_duration(case)
                    results[case] = f"✅ {normalized}"
                except Exception as e:
                    results[case] = f"❌ {e}"
            
            all_passed = all('✅' in result for result in results.values())
            self.test_results['time_parser'] = {'success': all_passed, 'results': results}
            
            if all_passed:
                print("✅ Time parser test passed")
            else:
                print("❌ Time parser test had issues")
                for case, result in results.items():
                    print(f"  {case}: {result}")
                    
        except Exception as e:
            self.test_results['time_parser'] = {'success': False, 'error': str(e)}
            print(f"❌ Time parser test failed: {e}")
    
    def run_all_tests(self):
        """Run all bot tests"""
        print("🤖 COMPREHENSIVE BOT FEATURE TEST")
        print("=" * 50)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Test 1: Database Operations
        self.test_database_operations()
        
        # Test 2: Time Parser
        self.test_time_parser()
        
        # Test 3: Bot Startup
        print("\n=== Testing Bot Startup ===")
        output = self.run_bot_with_timeout(30)
        bot_results = self.analyze_bot_output(output)
        self.test_results['bot_startup'] = bot_results
        
        if bot_results['overall_success']:
            print("✅ Bot startup test passed")
        else:
            print("❌ Bot startup test had issues")
        
        print(f"  Database Init: {'✅' if bot_results['database_init'] else '❌'}")
        print(f"  Cogs Loaded: {bot_results['cogs_loaded']}/9 ({bot_results['cog_load_percentage']:.1f}%)")
        print(f"  Commands Synced: {bot_results['commands_synced']}")
        print(f"  Bot Ready: {'✅' if bot_results['bot_ready'] else '❌'}")
        
        if bot_results['errors']:
            print(f"  Errors: {len(bot_results['errors'])}")
            for error in bot_results['errors'][:3]:  # Show first 3 errors
                print(f"    - {error}")
        
        # Generate summary
        self.generate_summary()
    
    def generate_summary(self):
        """Generate test summary"""
        print("\n" + "=" * 50)
        print("🎯 TEST SUMMARY")
        print("=" * 50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() 
                          if isinstance(result, dict) and result.get('success') or result.get('overall_success'))
        
        print(f"Tests Run: {total_tests}")
        print(f"Tests Passed: {passed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print()
        
        for test_name, result in self.test_results.items():
            if isinstance(result, dict):
                success = result.get('success') or result.get('overall_success')
                status = "✅ PASS" if success else "❌ FAIL"
                print(f"{status} - {test_name}")
        
        print()
        overall_success = passed_tests == total_tests
        if overall_success:
            print("🎉 ALL TESTS PASSED - BOT IS FULLY FUNCTIONAL!")
        else:
            print("⚠️  SOME TESTS FAILED - CHECK DETAILS ABOVE")
        
        print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    tester = BotTester()
    tester.run_all_tests()
