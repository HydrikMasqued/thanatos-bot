#!/usr/bin/env python3
import sys
import asyncio
sys.path.append('.')
from cogs.contributions import ContributionSystem

async def test_menu_system():
    print("Testing menu system validation...")
    
    # Test contribution system categories
    print("\n=== Testing Contribution Categories ===")
    
    # Create a mock bot instance
    class MockBot:
        def __init__(self):
            pass
        
        def get_guild(self, guild_id):
            return None
    
    contrib_system = ContributionSystem(MockBot())
    
    try:
        categories = await contrib_system._get_available_categories(123456789)
        print(f"✅ Categories loaded: {len(categories)} total")
        
        # Check that Mech Parts is NOT in categories
        category_names = [cat['name'] for cat in categories]
        print(f"Category names: {category_names}")
        
        if "Mech Parts" in category_names:
            print("❌ Mech Parts still exists in categories!")
        else:
            print("✅ Mech Parts successfully removed")
        
        # Check expected categories exist
        expected_misc_categories = ["Heist Items", "Dirty Cash", "Drug Items", "Mech Shop", "Crafting Items"]
        missing_categories = [cat for cat in expected_misc_categories if cat not in category_names]
        
        if missing_categories:
            print(f"❌ Missing expected categories: {missing_categories}")
        else:
            print("✅ All expected Misc categories present")
        
        # Test category structure
        misc_categories = [cat for cat in categories if cat['header'] == '📦 Misc Items']
        print(f"✅ Misc Items categories: {len(misc_categories)}")
        
        for cat in misc_categories:
            print(f"  - {cat['name']}: header='{cat['header']}', type='{cat['type']}'")
        
    except Exception as e:
        print(f"❌ Category system error: {e}")
    
    print("\n=== Testing Thread ID Mappings ===")
    
    # Test specific thread IDs from _find_category_thread method
    try:
        # Check the thread mappings directly
        expected_mappings = {
            "Heist Items": 1368632475986694224,
            "Dirty Cash": 1380363715983048826,
            "Drug Items": 1389785875789119521,
            "Mech Shop": 1389787215042842714,
            "Crafting Items": 1366606110315778118,
        }
        
        print("Expected thread mappings:")
        for category, thread_id in expected_mappings.items():
            print(f"  - {category}: {thread_id}")
        
        # Validate these are in our code by checking the source
        import inspect
        from cogs.contributions import ContributionModal
        source = inspect.getsource(ContributionModal._find_category_thread)
        
        all_mappings_found = True
        for category, thread_id in expected_mappings.items():
            if str(thread_id) not in source:
                print(f"❌ Thread ID {thread_id} for {category} not found in code")
                all_mappings_found = False
        
        if all_mappings_found:
            print("✅ All expected thread IDs found in code")
        
        # Check that Mech Parts thread ID is NOT duplicated
        if "Mech Parts" in source:
            print("❌ Mech Parts still referenced in thread mapping code")
        else:
            print("✅ Mech Parts references removed from thread mapping")
        
    except Exception as e:
        print(f"❌ Thread mapping test error: {e}")
    
    print("\n🎉 Menu system validation completed!")

if __name__ == "__main__":
    asyncio.run(test_menu_system())
