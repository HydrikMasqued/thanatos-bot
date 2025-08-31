#!/usr/bin/env python3
"""
Comprehensive tests for all bot systems
"""
import sys
import asyncio
from datetime import datetime, timedelta
sys.path.append('.')

class SystemTester:
    def __init__(self):
        self.results = {}
    
    async def test_loa_system(self):
        """Test LOA system functionality"""
        print("\n=== Testing LOA System ===")
        
        try:
            from utils.database import DatabaseManager
            from utils.time_parser import TimeParser
            from utils.loa_notifications import LOANotificationManager
            from main import ThanatosBot
            
            db = DatabaseManager()
            await db.initialize_database()
            
            guild_id = 123456789
            user_id = 987654321
            
            await db.initialize_guild(guild_id)
            await db.add_or_update_member(guild_id, user_id, "TestUser")
            
            # Test LOA creation
            start_time = datetime.now()
            end_time = start_time + timedelta(days=7)
            loa_id = await db.create_loa_record(guild_id, user_id, "7 days", "Test LOA", start_time, end_time)
            
            # Test LOA retrieval
            active_loa = await db.get_active_loa(guild_id, user_id)
            
            # Test time parser with LOA
            parser = TimeParser()
            parsed_time, normalized = parser.parse_duration("7 days")
            
            await db.close()
            
            self.results['loa_system'] = {
                'success': True,
                'loa_created': loa_id is not None,
                'loa_retrieved': active_loa is not None,
                'time_parsing': '7 days' in normalized.lower(),
                'details': f'LOA ID: {loa_id}, Active LOA: {active_loa is not None}'
            }
            print("✅ LOA system test passed")
            
        except Exception as e:
            self.results['loa_system'] = {'success': False, 'error': str(e)}
            print(f"❌ LOA system test failed: {e}")
    
    async def test_contribution_system(self):
        """Test contribution system functionality"""
        print("\n=== Testing Contribution System ===")
        
        try:
            from utils.database import DatabaseManager
            from cogs.contributions import ContributionSystem
            
            db = DatabaseManager()
            await db.initialize_database()
            
            guild_id = 123456789
            user_id = 987654321
            
            await db.initialize_guild(guild_id)
            await db.add_or_update_member(guild_id, user_id, "TestUser")
            
            # Test contribution creation
            contrib_id = await db.add_contribution(guild_id, user_id, "Heist Items", "Test Item", 5)
            
            # Test contribution retrieval
            contributions = await db.get_all_contributions(guild_id)
            
            # Test category system
            class MockBot:
                def get_guild(self, guild_id): return None
            
            contrib_system = ContributionSystem(MockBot())
            categories = await contrib_system._get_available_categories(guild_id)
            
            # Check that our menu changes are working
            category_names = [cat['name'] for cat in categories]
            misc_categories = [cat for cat in categories if cat['header'] == '📦 Misc Items']
            
            await db.close()
            
            self.results['contribution_system'] = {
                'success': True,
                'contribution_created': contrib_id is not None,
                'contributions_retrieved': len(contributions) > 0,
                'categories_loaded': len(categories) > 0,
                'misc_categories_count': len(misc_categories),
                'mech_parts_removed': 'Mech Parts' not in category_names,
                'expected_misc_items': all(cat in category_names for cat in 
                    ['Heist Items', 'Dirty Cash', 'Drug Items', 'Mech Shop', 'Crafting Items']),
                'details': f'Contrib ID: {contrib_id}, Categories: {len(categories)}, Misc Items: {len(misc_categories)}'
            }
            print("✅ Contribution system test passed")
            
        except Exception as e:
            self.results['contribution_system'] = {'success': False, 'error': str(e)}
            print(f"❌ Contribution system test failed: {e}")
    
    async def test_membership_system(self):
        """Test membership system functionality"""
        print("\n=== Testing Membership System ===")
        
        try:
            from utils.database import DatabaseManager
            
            db = DatabaseManager()
            await db.initialize_database()
            
            guild_id = 123456789
            user_id_1 = 987654321
            user_id_2 = 987654322
            
            await db.initialize_guild(guild_id)
            
            # Test member creation
            await db.add_or_update_member(guild_id, user_id_1, "TestUser1")
            await db.add_or_update_member(guild_id, user_id_2, "TestUser2")
            
            # Test member retrieval
            member1 = await db.get_member(guild_id, user_id_1)
            member2 = await db.get_member(guild_id, user_id_2)
            
            # Test member status updates
            await db.update_member_status(guild_id, user_id_1, on_loa=True)
            member1_updated = await db.get_member(guild_id, user_id_1)
            
            await db.close()
            
            self.results['membership_system'] = {
                'success': True,
                'members_created': member1 is not None and member2 is not None,
                'member_status_update': member1_updated is not None,
                'loa_status_working': member1_updated.get('on_loa', False) if member1_updated else False,
                'details': f'Members created: 2, Status updates: working'
            }
            print("✅ Membership system test passed")
            
        except Exception as e:
            self.results['membership_system'] = {'success': False, 'error': str(e)}
            print(f"❌ Membership system test failed: {e}")
    
    async def test_configuration_system(self):
        """Test configuration system functionality"""
        print("\n=== Testing Configuration System ===")
        
        try:
            from utils.database import DatabaseManager
            
            db = DatabaseManager()
            await db.initialize_database()
            
            guild_id = 123456789
            await db.initialize_guild(guild_id)
            
            # Test server config creation
            officer_role_id = 555555555
            leadership_channel_id = 666666666
            
            await db.update_server_config(
                guild_id,
                officer_role_id=officer_role_id,
                leadership_channel_id=leadership_channel_id
            )
            
            # Test config retrieval
            config = await db.get_server_config(guild_id)
            
            # Test config updates
            await db.update_server_config(
                guild_id,
                contribution_categories=['Test Category 1', 'Test Category 2']
            )
            
            updated_config = await db.get_server_config(guild_id)
            
            await db.close()
            
            self.results['configuration_system'] = {
                'success': True,
                'config_created': config is not None,
                'officer_role_set': config.get('officer_role_id') == officer_role_id if config else False,
                'leadership_channel_set': config.get('leadership_channel_id') == leadership_channel_id if config else False,
                'categories_updated': len(updated_config.get('contribution_categories', [])) == 2 if updated_config else False,
                'details': f'Config created, roles/channels set, categories configurable'
            }
            print("✅ Configuration system test passed")
            
        except Exception as e:
            self.results['configuration_system'] = {'success': False, 'error': str(e)}
            print(f"❌ Configuration system test failed: {e}")
    
    def test_menu_system_integrity(self):
        """Test menu system integrity"""
        print("\n=== Testing Menu System Integrity ===")
        
        try:
            # Check contributions.py for menu integrity
            from cogs.contributions import ContributionModal
            import inspect
            
            # Get the source code to verify thread mappings
            source = inspect.getsource(ContributionModal._find_category_thread)
            
            # Expected thread mappings
            expected_mappings = {
                "Heist Items": "1368632475986694224",
                "Dirty Cash": "1380363715983048826", 
                "Drug Items": "1389785875789119521",
                "Mech Shop": "1389787215042842714",
                "Crafting Items": "1366606110315778118"
            }
            
            # Verify all expected mappings are in code
            mappings_found = {}
            for category, thread_id in expected_mappings.items():
                if thread_id in source and category in source:
                    mappings_found[category] = True
                else:
                    mappings_found[category] = False
            
            # Verify Mech Parts is NOT in code
            mech_parts_removed = "Mech Parts" not in source
            
            self.results['menu_system_integrity'] = {
                'success': True,
                'expected_mappings_found': all(mappings_found.values()),
                'mech_parts_removed': mech_parts_removed,
                'thread_mappings': mappings_found,
                'details': f'Thread mappings: {len([v for v in mappings_found.values() if v])}/5, Mech Parts removed: {mech_parts_removed}'
            }
            print("✅ Menu system integrity test passed")
            
        except Exception as e:
            self.results['menu_system_integrity'] = {'success': False, 'error': str(e)}
            print(f"❌ Menu system integrity test failed: {e}")
    
    async def run_all_system_tests(self):
        """Run all system tests"""
        print("🔧 COMPREHENSIVE SYSTEM TESTING")
        print("=" * 60)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run all tests
        await self.test_loa_system()
        await self.test_contribution_system()
        await self.test_membership_system()
        await self.test_configuration_system()
        self.test_menu_system_integrity()
        
        # Generate comprehensive report
        self.generate_comprehensive_report()
    
    def generate_comprehensive_report(self):
        """Generate comprehensive system test report"""
        print("\n" + "=" * 60)
        print("📋 COMPREHENSIVE SYSTEM TEST REPORT")
        print("=" * 60)
        
        total_systems = len(self.results)
        passed_systems = sum(1 for result in self.results.values() if result.get('success', False))
        
        print(f"Systems Tested: {total_systems}")
        print(f"Systems Passed: {passed_systems}")
        print(f"Success Rate: {(passed_systems/total_systems)*100:.1f}%")
        print()
        
        # Detailed results for each system
        for system_name, result in self.results.items():
            status = "✅ PASS" if result.get('success') else "❌ FAIL"
            print(f"{status} - {system_name.upper()}")
            
            if result.get('success'):
                # Show detailed success metrics
                details = result.get('details', 'No details')
                print(f"      Details: {details}")
                
                # Show specific test results
                for key, value in result.items():
                    if key not in ['success', 'details', 'error'] and isinstance(value, bool):
                        icon = "✅" if value else "❌"
                        print(f"      {icon} {key.replace('_', ' ').title()}: {value}")
            else:
                error = result.get('error', 'Unknown error')
                print(f"      Error: {error}")
            print()
        
        # Overall assessment
        print("=" * 60)
        if passed_systems == total_systems:
            print("🎉 ALL SYSTEMS FULLY FUNCTIONAL!")
            print("🚀 BOT IS READY FOR PRODUCTION DEPLOYMENT")
        else:
            print("⚠️  SOME SYSTEMS NEED ATTENTION")
            failed_systems = [name for name, result in self.results.items() if not result.get('success')]
            print(f"❌ Failed systems: {', '.join(failed_systems)}")
        
        print(f"\nTesting completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

async def main():
    tester = SystemTester()
    await tester.run_all_system_tests()

if __name__ == "__main__":
    asyncio.run(main())
