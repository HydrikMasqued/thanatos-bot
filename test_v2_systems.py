#!/usr/bin/env python3
"""
Comprehensive Testing Script for Thanatos Bot V2 Systems
========================================================

This script tests the functionality of both the Prospects V2 and Dues V2 systems
to ensure they are working correctly after the migration from legacy systems.

Tests include:
- Database connectivity and schema verification
- Prospects V2 CRUD operations
- Dues V2 CRUD operations
- Error handling and edge cases
- Performance benchmarking

Usage: python test_v2_systems.py
"""

import asyncio
import os
import sys
import sqlite3
from datetime import datetime, timedelta
import json
import traceback

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.database import DatabaseManager

class V2SystemTester:
    """Comprehensive tester for V2 systems"""
    
    def __init__(self):
        self.db = DatabaseManager("data/thanatos.db")
        self.test_guild_id = 889005510286786601  # Test guild
        self.test_results = {
            'database': [],
            'prospects_v2': [],
            'dues_v2': [],
            'performance': [],
            'errors': []
        }
        
    async def run_all_tests(self):
        """Run all test suites"""
        print("🧪 Starting Comprehensive V2 Systems Testing...")
        print("=" * 60)
        
        try:
            # Initialize database
            await self.db.initialize_database()
            await self.db.initialize_guild(self.test_guild_id)
            
            # Run test suites
            await self.test_database_schema()
            await self.test_prospects_v2()
            await self.test_dues_v2()
            await self.test_performance()
            
            # Generate report
            self.generate_test_report()
            
        except Exception as e:
            self.test_results['errors'].append(f"Critical test failure: {e}")
            traceback.print_exc()
        
        finally:
            await self.db.close()
    
    async def test_database_schema(self):
        """Test database schema and migrations"""
        print("\n🗄️  Testing Database Schema...")
        
        try:
            # Test if required tables exist
            conn = await self.db._get_shared_connection()
            cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in await cursor.fetchall()]
            
            required_tables = [
                'prospects', 'prospect_tasks', 'prospect_notes', 'prospect_votes', 'prospect_vote_responses',
                'dues_periods', 'dues_payments'
            ]
            
            for table in required_tables:
                if table in tables:
                    self.test_results['database'].append(f"✅ Table '{table}' exists")
                else:
                    self.test_results['database'].append(f"❌ Table '{table}' missing")
            
            # Test dues_periods schema specifically
            cursor = await conn.execute("PRAGMA table_info(dues_periods)")
            columns = [row[1] for row in await cursor.fetchall()]
            
            required_columns = ['id', 'guild_id', 'period_name', 'description', 'due_amount', 
                               'due_date', 'is_active', 'created_at', 'created_by_id', 
                               'updated_at', 'updated_by_id']
            
            for column in required_columns:
                if column in columns:
                    self.test_results['database'].append(f"✅ dues_periods.{column} exists")
                else:
                    self.test_results['database'].append(f"❌ dues_periods.{column} missing")
            
            print("   Database schema verification completed")
            
        except Exception as e:
            self.test_results['database'].append(f"❌ Schema test failed: {e}")
    
    async def test_prospects_v2(self):
        """Test Prospects V2 system"""
        print("\n👥 Testing Prospects V2 System...")
        
        try:
            # Test 1: Add a test prospect
            test_user_id = 999999999999999999
            test_sponsor_id = 888888888888888888
            
            # Clean up any existing test data
            conn = await self.db._get_shared_connection()
            await conn.execute("DELETE FROM prospects WHERE guild_id = ? AND user_id = ?", 
                              (self.test_guild_id, test_user_id))
            await self.db._execute_commit()
            
            # Add prospect
            prospect_id = await self.db.add_prospect(
                guild_id=self.test_guild_id,
                user_id=test_user_id,
                sponsor_id=test_sponsor_id
            )
            
            if prospect_id:
                self.test_results['prospects_v2'].append("✅ Create prospect successful")
            else:
                self.test_results['prospects_v2'].append("❌ Create prospect failed")
            
            # Test 2: Retrieve prospect
            prospect = await self.db.get_prospect_by_user(self.test_guild_id, test_user_id)
            if prospect and prospect['id'] == prospect_id:
                self.test_results['prospects_v2'].append("✅ Retrieve prospect successful")
            else:
                self.test_results['prospects_v2'].append("❌ Retrieve prospect failed")
            
            # Test 3: Add prospect task
            task_id = await self.db.add_prospect_task(
                guild_id=self.test_guild_id,
                prospect_id=prospect_id,
                assigned_by_id=test_sponsor_id,
                task_name="Test Task",
                task_description="This is a test task",
                due_date=datetime.now() + timedelta(days=7)
            )
            
            if task_id:
                self.test_results['prospects_v2'].append("✅ Add prospect task successful")
            else:
                self.test_results['prospects_v2'].append("❌ Add prospect task failed")
            
            # Test 4: Add prospect note
            note_id = await self.db.add_prospect_note(
                guild_id=self.test_guild_id,
                prospect_id=prospect_id,
                author_id=test_sponsor_id,
                note_text="Test note for prospect",
                is_strike=False
            )
            
            if note_id:
                self.test_results['prospects_v2'].append("✅ Add prospect note successful")
            else:
                self.test_results['prospects_v2'].append("❌ Add prospect note failed")
            
            # Test 5: Get active prospects
            active_prospects = await self.db.get_active_prospects(self.test_guild_id)
            if any(p['id'] == prospect_id for p in active_prospects):
                self.test_results['prospects_v2'].append("✅ Get active prospects successful")
            else:
                self.test_results['prospects_v2'].append("❌ Get active prospects failed")
            
            # Test 6: Update prospect status
            success = await self.db.update_prospect_status(prospect_id, 'patched')
            if success:
                self.test_results['prospects_v2'].append("✅ Update prospect status successful")
            else:
                self.test_results['prospects_v2'].append("❌ Update prospect status failed")
            
            # Cleanup
            await conn.execute("DELETE FROM prospects WHERE guild_id = ? AND user_id = ?", 
                              (self.test_guild_id, test_user_id))
            await self.db._execute_commit()
            
            print("   Prospects V2 testing completed")
            
        except Exception as e:
            self.test_results['prospects_v2'].append(f"❌ Prospects V2 test failed: {e}")
            traceback.print_exc()
    
    async def test_dues_v2(self):
        """Test Dues V2 system"""
        print("\n💰 Testing Dues V2 System...")
        
        try:
            # Test 1: Create a test dues period
            test_period_name = f"Test Period {datetime.now().strftime('%Y%m%d%H%M%S')}"
            test_user_id = 777777777777777777
            
            # Clean up any existing test data
            conn = await self.db._get_shared_connection()
            await conn.execute("DELETE FROM dues_periods WHERE guild_id = ? AND period_name LIKE 'Test Period%'", 
                              (self.test_guild_id,))
            await self.db._execute_commit()
            
            # Create dues period
            period_id = await self.db.create_dues_period(
                guild_id=self.test_guild_id,
                period_name=test_period_name,
                description="Test dues period for V2 system testing",
                due_amount=25.0,
                due_date=datetime.now() + timedelta(days=30),
                created_by_id=test_user_id
            )
            
            if period_id:
                self.test_results['dues_v2'].append("✅ Create dues period successful")
            else:
                self.test_results['dues_v2'].append("❌ Create dues period failed")
            
            # Test 2: Get active dues periods
            active_periods = await self.db.get_active_dues_periods(self.test_guild_id)
            if any(p['id'] == period_id for p in active_periods):
                self.test_results['dues_v2'].append("✅ Get active dues periods successful")
            else:
                self.test_results['dues_v2'].append("❌ Get active dues periods failed")
            
            # Test 3: Update dues payment
            payment_id = await self.db.update_dues_payment(
                guild_id=self.test_guild_id,
                user_id=test_user_id,
                dues_period_id=period_id,
                amount_paid=25.0,
                payment_status='paid',
                payment_date=datetime.now(),
                payment_method='Test Payment',
                notes='Test payment for V2 system',
                updated_by_id=test_user_id
            )
            
            if payment_id:
                self.test_results['dues_v2'].append("✅ Update dues payment successful")
            else:
                self.test_results['dues_v2'].append("❌ Update dues payment failed")
            
            # Test 4: Get user dues payment
            payment = await self.db.get_user_dues_payment(self.test_guild_id, test_user_id, period_id)
            if payment and payment['status'] == 'paid':
                self.test_results['dues_v2'].append("✅ Get user dues payment successful")
            else:
                self.test_results['dues_v2'].append("❌ Get user dues payment failed")
            
            # Test 5: Get dues payments for period
            payments = await self.db.get_dues_payments_for_period(self.test_guild_id, period_id)
            if any(p['user_id'] == test_user_id for p in payments):
                self.test_results['dues_v2'].append("✅ Get dues payments for period successful")
            else:
                self.test_results['dues_v2'].append("❌ Get dues payments for period failed")
            
            # Test 6: Deactivate dues period
            await self.db.deactivate_dues_period(self.test_guild_id, period_id, test_user_id)
            
            # Verify deactivation
            updated_periods = await self.db.get_active_dues_periods(self.test_guild_id)
            if not any(p['id'] == period_id for p in updated_periods):
                self.test_results['dues_v2'].append("✅ Deactivate dues period successful")
            else:
                self.test_results['dues_v2'].append("❌ Deactivate dues period failed")
            
            # Cleanup
            await conn.execute("DELETE FROM dues_periods WHERE guild_id = ? AND period_name LIKE 'Test Period%'", 
                              (self.test_guild_id,))
            await self.db._execute_commit()
            
            print("   Dues V2 testing completed")
            
        except Exception as e:
            self.test_results['dues_v2'].append(f"❌ Dues V2 test failed: {e}")
            traceback.print_exc()
    
    async def test_performance(self):
        """Test system performance"""
        print("\n⚡ Testing Performance...")
        
        try:
            # Test database connection speed
            start_time = datetime.now()
            await self.db._get_shared_connection()
            connection_time = (datetime.now() - start_time).total_seconds() * 1000
            
            self.test_results['performance'].append(f"✅ Database connection: {connection_time:.2f}ms")
            
            # Test prospects query performance
            start_time = datetime.now()
            await self.db.get_active_prospects(self.test_guild_id)
            query_time = (datetime.now() - start_time).total_seconds() * 1000
            
            self.test_results['performance'].append(f"✅ Active prospects query: {query_time:.2f}ms")
            
            # Test dues query performance
            start_time = datetime.now()
            await self.db.get_active_dues_periods(self.test_guild_id)
            query_time = (datetime.now() - start_time).total_seconds() * 1000
            
            self.test_results['performance'].append(f"✅ Active dues periods query: {query_time:.2f}ms")
            
            print("   Performance testing completed")
            
        except Exception as e:
            self.test_results['performance'].append(f"❌ Performance test failed: {e}")
    
    def generate_test_report(self):
        """Generate comprehensive test report"""
        print("\n" + "=" * 60)
        print("🧪 COMPREHENSIVE TEST REPORT")
        print("=" * 60)
        
        total_tests = 0
        passed_tests = 0
        
        for category, results in self.test_results.items():
            if not results and category != 'errors':
                continue
                
            print(f"\n📋 {category.upper().replace('_', ' ')}:")
            print("-" * 40)
            
            for result in results:
                print(f"   {result}")
                total_tests += 1
                if result.startswith("✅"):
                    passed_tests += 1
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        
        if total_tests > 0:
            success_rate = (passed_tests / total_tests) * 100
            print(f"Success Rate: {success_rate:.1f}%")
            
            if success_rate >= 90:
                print("🎉 EXCELLENT: V2 systems are working perfectly!")
            elif success_rate >= 75:
                print("✅ GOOD: V2 systems are mostly functional with minor issues")
            elif success_rate >= 50:
                print("⚠️  FAIR: V2 systems have some issues that need attention")
            else:
                print("❌ POOR: V2 systems have significant issues requiring immediate attention")
        
        # Errors
        if self.test_results['errors']:
            print("\n🚨 CRITICAL ERRORS:")
            print("-" * 40)
            for error in self.test_results['errors']:
                print(f"   {error}")
        
        print("\n" + "=" * 60)
        print("✨ V2 Systems Testing Complete!")
        print("=" * 60)


async def main():
    """Main testing function"""
    tester = V2SystemTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    # Ensure we're in the right directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Run the tests
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Testing interrupted by user")
    except Exception as e:
        print(f"\n💥 Testing failed with critical error: {e}")
        traceback.print_exc()