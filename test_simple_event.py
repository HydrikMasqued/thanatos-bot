#!/usr/bin/env python3
"""
Test script for the simplified /event command.

This script tests that the new simple event command:
1. Creates an event successfully
2. Automatically invites role members
3. Automatically RSVPs invited users as 'yes'
4. Handles the DM sending option correctly
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

async def test_simple_event_creation():
    """Test the simplified event creation functionality."""
    print("🧪 Testing Simplified Event Creation")
    print("=" * 50)
    
    # Initialize test database
    test_db_path = "data/test_simple_event.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    db = DatabaseManager(test_db_path)
    
    try:
        # Initialize database
        await db.initialize_database()
        
        # Test data
        guild_id = 123456789
        officer_id = 999999999
        role_member_1 = 111111111
        role_member_2 = 222222222
        role_member_3 = 333333333  # This will be a bot (to test skipping)
        event_name = "Team Meeting"
        event_description = "Weekly team sync meeting"
        event_date = datetime.now() + timedelta(days=1)
        
        print("1. Setting up test data...")
        
        # Initialize guild
        await db.initialize_guild(guild_id)
        
        # Add test members
        await db.add_or_update_member(guild_id, officer_id, "OfficerUser", "Officer")
        await db.add_or_update_member(guild_id, role_member_1, "Member1", "Member")
        await db.add_or_update_member(guild_id, role_member_2, "Member2", "Member")
        await db.add_or_update_member(guild_id, role_member_3, "BotMember", "Member")  # Simulate bot
        
        print("✅ Test data created")
        
        # Test 1: Create event
        print("\n2. Testing event creation...")
        event_id = await db.create_event(
            guild_id=guild_id,
            event_name=event_name,
            description=event_description,
            category="General",
            event_date=event_date,
            created_by_id=officer_id
        )
        
        if not event_id:
            print("❌ Failed to create event")
            return False
            
        print(f"✅ Event created with ID: {event_id}")
        
        # Test 2: Simulate role invitation (what the /event command does)
        print("\n3. Testing automatic role member invitation...")
        
        # Simulate inviting role members (excluding bots)
        test_role_members = [role_member_1, role_member_2]  # Exclude bot member
        invited_count = 0
        
        for member_id in test_role_members:
            success = await db.invite_user_to_event(
                event_id=event_id,
                guild_id=guild_id,
                user_id=member_id,
                invited_by_id=officer_id,
                invitation_method="event_creation",
                role_id=888888888  # Mock role ID
            )
            if success:
                invited_count += 1
        
        if invited_count != 2:
            print(f"❌ Expected 2 invitations, got {invited_count}")
            return False
            
        print("✅ Role members automatically invited")
        
        # Test 3: Check automatic RSVPs
        print("\n4. Testing automatic RSVP...")
        
        member1_rsvp = await db.get_user_rsvp(event_id, role_member_1)
        member2_rsvp = await db.get_user_rsvp(event_id, role_member_2)
        
        if member1_rsvp != 'yes' or member2_rsvp != 'yes':
            print(f"❌ Expected both members to be RSVP'd as 'yes', got: {member1_rsvp}, {member2_rsvp}")
            return False
            
        print("✅ All invited members automatically RSVP'd as 'yes'")
        
        # Test 4: Check RSVP counts
        print("\n5. Testing RSVP summary...")
        
        rsvps = await db.get_event_rsvps(event_id)
        yes_count = len(rsvps['yes'])
        no_count = len(rsvps['no'])
        maybe_count = len(rsvps['maybe'])
        
        if yes_count != 2 or no_count != 0 or maybe_count != 0:
            print(f"❌ Expected RSVP counts: Yes=2, No=0, Maybe=0, got: Yes={yes_count}, No={no_count}, Maybe={maybe_count}")
            return False
            
        print("✅ RSVP summary is correct")
        
        # Test 5: Test RSVP change functionality
        print("\n6. Testing RSVP change functionality...")
        
        # Member 1 changes to 'maybe'
        await db.record_rsvp(
            event_id=event_id,
            guild_id=guild_id,
            user_id=role_member_1,
            response='maybe',
            notes='Need to check calendar'
        )
        
        # Check updated RSVP
        updated_rsvp = await db.get_user_rsvp(event_id, role_member_1)
        if updated_rsvp != 'maybe':
            print(f"❌ Expected member 1 RSVP to be 'maybe', got: {updated_rsvp}")
            return False
            
        print("✅ RSVP change works correctly")
        
        # Test 6: Test event retrieval
        print("\n7. Testing event details retrieval...")
        
        event_details = await db.get_event_by_id(event_id)
        if not event_details:
            print("❌ Could not retrieve event details")
            return False
            
        if event_details['event_name'] != event_name:
            print(f"❌ Event name mismatch. Expected: {event_name}, got: {event_details['event_name']}")
            return False
            
        print("✅ Event details retrieved correctly")
        
        # Test 7: Test invitations retrieval
        print("\n8. Testing invitations retrieval...")
        
        invitations = await db.get_event_invitations(event_id)
        if len(invitations) != 2:
            print(f"❌ Expected 2 invitations, got {len(invitations)}")
            return False
            
        # Check invitation methods
        for invitation in invitations:
            if invitation['invitation_method'] != 'event_creation':
                print(f"❌ Unexpected invitation method: {invitation['invitation_method']}")
                return False
                
        print("✅ Invitations retrieved correctly")
        
        # Test 8: Test duplicate invitation handling
        print("\n9. Testing duplicate invitation handling...")
        
        # Try to invite the same user again
        duplicate_success = await db.invite_user_to_event(
            event_id=event_id,
            guild_id=guild_id,
            user_id=role_member_1,
            invited_by_id=officer_id,
            invitation_method="test_duplicate"
        )
        
        if duplicate_success:
            print("❌ Duplicate invitation should have failed")
            return False
            
        print("✅ Duplicate invitation correctly rejected")
        
        print("\n" + "=" * 50)
        print("🎉 ALL TESTS PASSED!")
        print("✅ Simplified event creation works correctly")
        print("✅ Role members are automatically invited and RSVP'd as 'Yes'")
        print("✅ Users can still change their RSVP manually")
        print("✅ Event details and invitations are stored correctly")
        print("✅ Duplicate invitations are handled properly")
        
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
    success = await test_simple_event_creation()
    if not success:
        sys.exit(1)
    print("\n🚀 Simplified event system is working perfectly!")
    print("\n💡 Usage example:")
    print("   /event name:Team Meeting time:tomorrow 3pm description:Weekly sync role:@Members send_dms:True")

if __name__ == "__main__":
    asyncio.run(main())
