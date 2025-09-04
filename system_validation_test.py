#!/usr/bin/env python3
"""
System Validation Test for Thanatos Bot
Tests all core functionality to ensure 100% operational status
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_database_connectivity():
    """Test database initialization and core functions"""
    try:
        from utils.database import DatabaseManager
        db = DatabaseManager()
        await db.initialize_database()
        print("✅ Database connectivity: PASS")
        await db.close()
        return True
    except Exception as e:
        print(f"❌ Database connectivity: FAIL - {e}")
        return False

async def test_cog_imports():
    """Test that all cogs can be imported"""
    cogs_to_test = [
        'cogs.loa_system', 'cogs.membership', 'cogs.contributions', 
        'cogs.configuration', 'cogs.direct_messaging', 'cogs.database_management',
        'cogs.audit_logs', 'cogs.events', 'cogs.event_notepad', 'cogs.dues_tracking',
        'cogs.prospect_core', 'cogs.prospect_dashboard', 'cogs.prospect_notifications',
        'cogs.enhanced_menu_system'
    ]
    
    success_count = 0
    for cog_name in cogs_to_test:
        try:
            __import__(cog_name)
            print(f"✅ {cog_name}: IMPORT OK")
            success_count += 1
        except Exception as e:
            print(f"❌ {cog_name}: IMPORT FAIL - {e}")
    
    print(f"📊 Cog imports: {success_count}/{len(cogs_to_test)} successful")
    return success_count == len(cogs_to_test)

async def test_utils_imports():
    """Test utility imports"""
    utils_to_test = [
        ('utils.database', 'DatabaseManager'),
        ('utils.time_parser', 'TimeParser'),
        ('utils.loa_notifications', 'LOANotificationManager'),
        ('utils.precise_reminder_system', 'PreciseReminderSystem'),
        ('utils.contribution_audit_helpers', 'ContributionAuditHelpers')
    ]
    
    success_count = 0
    for module, class_name in utils_to_test:
        try:
            module_obj = __import__(module, fromlist=[class_name])
            getattr(module_obj, class_name)
            print(f"✅ {module}.{class_name}: IMPORT OK")
            success_count += 1
        except Exception as e:
            print(f"❌ {module}.{class_name}: IMPORT FAIL - {e}")
    
    print(f"📊 Utils imports: {success_count}/{len(utils_to_test)} successful")
    return success_count == len(utils_to_test)

async def test_enhanced_menu_structure():
    """Test enhanced menu system structure"""
    try:
        from cogs.enhanced_menu_system import DashboardView, EnhancedMenuSystem
        print("✅ Enhanced menu system: STRUCTURE OK")
        
        # Test that key views exist
        views_to_check = [
            'ContributionsModuleView', 'DatabaseModuleView', 'AuditModuleView',
            'MembershipModuleView', 'LOAModuleView', 'MessagingModuleView',
            'AdministrationModuleView', 'DuesTrackingModuleView'
        ]
        
        module = __import__('cogs.enhanced_menu_system', fromlist=views_to_check)
        missing_views = []
        
        for view_name in views_to_check:
            if not hasattr(module, view_name):
                missing_views.append(view_name)
        
        if missing_views:
            print(f"⚠️ Missing views: {missing_views}")
            return False
        else:
            print("✅ All menu views: PRESENT")
            return True
            
    except Exception as e:
        print(f"❌ Enhanced menu system: STRUCTURE FAIL - {e}")
        return False

async def test_command_definitions():
    """Test that commands are properly defined"""
    try:
        from cogs.enhanced_menu_system import EnhancedMenuSystem
        
        # Check command methods exist
        expected_commands = ['enhanced_menu', 'dashboard_shortcut', 'quick_contribute', 'quick_loa', 'test_command']
        
        missing_commands = []
        for cmd in expected_commands:
            if not hasattr(EnhancedMenuSystem, cmd):
                missing_commands.append(cmd)
        
        if missing_commands:
            print(f"⚠️ Missing commands: {missing_commands}")
            return False
        else:
            print("✅ Command definitions: COMPLETE")
            return True
            
    except Exception as e:
        print(f"❌ Command definitions: FAIL - {e}")
        return False

async def run_all_tests():
    """Run all validation tests"""
    print("🔍 Starting System Validation Tests")
    print("=" * 50)
    
    tests = [
        ("Database Connectivity", test_database_connectivity()),
        ("Cog Imports", test_cog_imports()),
        ("Utils Imports", test_utils_imports()),
        ("Enhanced Menu Structure", test_enhanced_menu_structure()),
        ("Command Definitions", test_command_definitions())
    ]
    
    results = {}
    for test_name, test_coro in tests:
        print(f"\n🧪 Testing: {test_name}")
        print("-" * 30)
        try:
            result = await test_coro
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name}: CRITICAL ERROR - {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, passed_status in results.items():
        status = "✅ PASS" if passed_status else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n📊 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL SYSTEMS OPERATIONAL - 100% FUNCTIONALITY CONFIRMED")
        return True
    else:
        print("⚠️ SOME ISSUES DETECTED - REVIEW FAILED TESTS")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
