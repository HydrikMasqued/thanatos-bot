#!/usr/bin/env python3
import sys
import asyncio
import json
from datetime import datetime, timedelta
sys.path.append('.')
from utils.database import DatabaseManager
from utils.time_parser import TimeParser
from utils.loa_notifications import LOANotificationManager

async def test_core_functions():
    print("Testing core functionality...")
    
    # Test Database Operations
    print("\n=== Testing Database Operations ===")
    db = DatabaseManager()
    await db.initialize_database()
    
    guild_id = 123456789
    user_id = 987654321
    
    await db.initialize_guild(guild_id)
    print("✅ Guild initialization")
    
    # Test member operations
    await db.add_or_update_member(guild_id, user_id, "TestUser")
    member = await db.get_member(guild_id, user_id)
    print(f"✅ Member operations: {member is not None}")
    
    # Test contribution operations
    try:
        contrib_id = await db.add_contribution(guild_id, user_id, "Test Category", "Test Item", 5)
        print(f"✅ Add contribution: {contrib_id is not None}")
        
        contributions = await db.get_all_contributions(guild_id)
        print(f"✅ Get contributions: {len(contributions) > 0}")
    except Exception as e:
        print(f"❌ Contribution operations error: {e}")
    
    # Test LOA operations
    try:
        start_date = datetime.now()
        end_date = datetime.now() + timedelta(days=7)
        loa_id = await db.create_loa_record(guild_id, user_id, "7 days", "Test LOA", start_date, end_date)
        print(f"✅ Create LOA: {loa_id is not None}")
        
        loa = await db.get_active_loa(guild_id, user_id)
        print(f"✅ Get LOA: {loa is not None}")
    except Exception as e:
        print(f"❌ LOA operations error: {e}")
    
    await db.close()
    
    # Test Time Parser
    print("\n=== Testing Time Parser ===")
    try:
        time_parser = TimeParser()
        
        # Test various time formats
        test_cases = [
            "7 days",
            "2 weeks",
            "1 month",
            "3d",
            "1w 2d",
            "30d"
        ]
        
        for test in test_cases:
            try:
                result = time_parser.parse_duration(test)
                print(f"✅ Parse '{test}': {result is not None}")
            except Exception as e:
                print(f"❌ Parse '{test}': {e}")
                
    except Exception as e:
        print(f"❌ Time parser initialization: {e}")
    
    print("\n🎉 Core functionality tests completed!")

if __name__ == "__main__":
    asyncio.run(test_core_functions())
