#!/usr/bin/env python3
"""
Test script for automatic RSVP functionality.

This script tests that:
1. Users are automatically RSVP'd as 'yes' when invited to events
2. Users can manually change their RSVP response after being automatically invited
3. The database handles the automatic RSVP correctly
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add the project directory to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.database import DatabaseManager

async def test_automatic_rsvp():
    """Test the automatic RSVP functionality."""
    print("🧪 Testing Automatic RSVP Functionality")
    print("=" * 50)
    
    # Initialize test database
    test_db_path = "data/test_auto_rsvp.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    db = DatabaseManager(test_db_path)
    
    try:
        # Initialize database
        await db.initialize_database()
        
        # Test data
        guild_id = 123456789
        user_id_1 = 111111111
        user_id_2 = 222222222
        invited_by_id = 333333333
        event_name = "Test Event"
        event_description = "This is a test event"
        event_category = "Testing"
        event_date = datetime.now() + timedelta(days=1)
        
        print("1. Setting up test data...")
        
        # Initialize guild
        await db.initialize_guild(guild_id)
        
        # Add test members
        await db.add_or_update_member(guild_id, user_id_1, "TestUser1", "Test Rank 1")
        await db.add_or_update_member(guild_id, user_id_2, "TestUser2", "Test Rank 2")
        await db.add_or_update_member(guild_id, invited_by_id, "TestOfficer", "Officer")
        
        print("✅ Test data created")
        
        # Create test event
        print("\n2. Creating test event...")
        event_id = await db.create_event(
            guild_id=guild_id,
            event_name=event_name,
            description=event_description,
            category=event_category,
            event_date=event_date,
            created_by_id=invited_by_id
        )
        print(f"✅ Event created with ID: {event_id}")
        
        # Test 1: Invite user and check automatic RSVP
        print("\n3. Testing automatic RSVP on invitation...")
        
        # Invite user 1
        success = await db.invite_user_to_event(
            event_id=event_id,
            guild_id=guild_id,
            user_id=user_id_1,
            invited_by_id=invited_by_id,
            invitation_method="test_invite"
        )
        
        if not success:
            print("❌ Failed to invite user 1")
            return False
            
        print("✅ User 1 invited successfully")
        
        # Check if user was automatically RSVP'd as 'yes'
        user1_rsvp = await db.get_user_rsvp(event_id, user_id_1)
        if user1_rsvp != 'yes':
            print(f"❌ User 1 RSVP should be 'yes', but got: {user1_rsvp}")
            return False
            
        print("✅ User 1 automatically RSVP'd as 'yes'")
        
        # Test 2: Invite second user
        print("\n4. Testing second user invitation...")
        
        success = await db.invite_user_to_event(
            event_id=event_id,
            guild_id=guild_id,
            user_id=user_id_2,
            invited_by_id=invited_by_id,
            invitation_method="test_invite"
        )
        
        if not success:
            print("❌ Failed to invite user 2")
            return False
            
        user2_rsvp = await db.get_user_rsvp(event_id, user_id_2)
        if user2_rsvp != 'yes':
            print(f"❌ User 2 RSVP should be 'yes', but got: {user2_rsvp}")
            return False
            
        print("✅ User 2 automatically RSVP'd as 'yes'")
        
        # Test 3: Manual RSVP change
        print("\n5. Testing manual RSVP change...")
        
        # User 1 changes RSVP to 'no'
        await db.record_rsvp(
            event_id=event_id,
            guild_id=guild_id,
            user_id=user_id_1,
            response='no',
            notes='Changed my mind'
        )
        
        # Check the change
        user1_rsvp_after = await db.get_user_rsvp(event_id, user_id_1)
        if user1_rsvp_after != 'no':
            print(f"❌ User 1 RSVP should be 'no' after manual change, but got: {user1_rsvp_after}")
            return False
            
        print("✅ User 1 successfully changed RSVP to 'no'")
        
        # User 2 changes RSVP to 'maybe'
        await db.record_rsvp(
            event_id=event_id,
            guild_id=guild_id,
            user_id=user_id_2,
            response='maybe',
            notes='Need to check schedule'
        )
        
        user2_rsvp_after = await db.get_user_rsvp(event_id, user_id_2)
        if user2_rsvp_after != 'maybe':
            print(f"❌ User 2 RSVP should be 'maybe' after manual change, but got: {user2_rsvp_after}")
            return False
            
        print("✅ User 2 successfully changed RSVP to 'maybe'")
        
        # Test 4: Check RSVP summary
        print("\n6. Testing RSVP summary...")
        
        rsvps = await db.get_event_rsvps(event_id)
        
        yes_count = len(rsvps['yes'])
        no_count = len(rsvps['no'])
        maybe_count = len(rsvps['maybe'])
        
        print(f"RSVP Summary: Yes={yes_count}, No={no_count}, Maybe={maybe_count}")
        
        if yes_count != 0 or no_count != 1 or maybe_count != 1:
            print(f"❌ Unexpected RSVP counts. Expected Yes=0, No=1, Maybe=1")
            return False
            
        print("✅ RSVP summary is correct")
        
        # Test 5: Try to invite already invited user (should fail)
        print("\n7. Testing duplicate invitation handling...")
        
        duplicate_success = await db.invite_user_to_event(
            event_id=event_id,
            guild_id=guild_id,
            user_id=user_id_1,
            invited_by_id=invited_by_id,
            invitation_method="test_duplicate"
        )
        
        if duplicate_success:
            print("❌ Duplicate invitation should have failed but succeeded")
            return False
            
        print("✅ Duplicate invitation correctly rejected")
        
        # Test 6: Verify automatic RSVP notes
        print("\n8. Testing automatic RSVP notes...")
        
        # Create another user and invite them
        user_id_3 = 444444444
        await db.add_or_update_member(guild_id, user_id_3, "TestUser3", "Test Rank 3")
        
        await db.invite_user_to_event(
            event_id=event_id,
            guild_id=guild_id,
            user_id=user_id_3,
            invited_by_id=invited_by_id,
            invitation_method="test_notes"
        )
        
        # Get the RSVP details
        rsvps_detailed = await db.get_event_rsvps(event_id)
        user3_rsvp_found = False
        
        for rsvp in rsvps_detailed['yes']:
            if rsvp['user_id'] == user_id_3:
                if 'Automatically RSVP\'d upon invitation' in rsvp.get('notes', ''):
                    user3_rsvp_found = True
                    break
        
        if not user3_rsvp_found:
            print("❌ Could not find automatic RSVP notes for user 3")
            return False
            
        print("✅ Automatic RSVP notes are correct")
        
        print("\n" + "=" * 50)
        print("🎉 ALL TESTS PASSED!")
        print("✅ Users are automatically RSVP'd as 'yes' when invited")
        print("✅ Users can change their RSVP manually after automatic invitation")
        print("✅ Duplicate invitations are handled correctly")
        print("✅ Automatic RSVP notes are set properly")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await db.close()
        # Clean up test database
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

async def main():
    """Run the test."""
    success = await test_automatic_rsvp()
    if not success:
        sys.exit(1)
    print("\n🚀 Automatic RSVP functionality is working correctly!")

if __name__ == "__main__":
    asyncio.run(main())
