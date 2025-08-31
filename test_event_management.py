#!/usr/bin/env python3
"""
Test Script for Event Management System
Validates all event management functionality without requiring a live Discord bot.
"""

import asyncio
import sqlite3
import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.database import DatabaseManager

class EventManagementTester:
    def __init__(self):
        self.test_db_path = "data/test_event_management.db"
        self.db_manager = None
        self.test_guild_id = 123456789
        self.test_user_id = 987654321
        self.test_officer_id = 111111111
        self.test_role_id = 222222222
        
    async def setup(self):
        """Initialize test database"""
        print("🔧 Setting up test environment...")
        
        # Remove existing test database
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        
        # Initialize database manager with test database
        self.db_manager = DatabaseManager(self.test_db_path)
        await self.db_manager.initialize_database()
        await self.db_manager.initialize_guild(self.test_guild_id)
        
        # Add test members
        await self.db_manager.add_or_update_member(
            self.test_guild_id, self.test_user_id, "TestUser", "Member"
        )
        await self.db_manager.add_or_update_member(
            self.test_guild_id, self.test_officer_id, "TestOfficer", "Officer"
        )
        
        print("✅ Test environment setup complete")
    
    async def teardown(self):
        """Clean up test resources"""
        if self.db_manager:
            await self.db_manager.close()
        
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        
        print("🧹 Test environment cleaned up")
    
    async def test_event_creation(self):
        """Test creating events"""
        print("\n📅 Testing Event Creation...")
        
        try:
            # Test basic event creation
            event_id = await self.db_manager.create_event(
                guild_id=self.test_guild_id,
                event_name="Test Event",
                description="This is a test event",
                category="Testing",
                event_date=datetime.now() + timedelta(days=1),
                location="Test Location",
                max_attendees=50,
                created_by_id=self.test_officer_id,
                reminder_hours_before=24
            )
            
            assert event_id is not None, "Event creation should return an ID"
            print(f"  ✅ Basic event created with ID: {event_id}")
            
            # Test retrieving the event
            event = await self.db_manager.get_event_by_id(event_id)
            assert event is not None, "Event should be retrievable"
            assert event['event_name'] == "Test Event", "Event name should match"
            assert event['description'] == "This is a test event", "Event description should match"
            assert event['category'] == "Testing", "Event category should match"
            assert event['location'] == "Test Location", "Event location should match"
            assert event['max_attendees'] == 50, "Max attendees should match"
            assert event['created_by_id'] == self.test_officer_id, "Creator ID should match"
            print(f"  ✅ Event retrieved and validated")
            
            # Test creating event without optional fields
            simple_event_id = await self.db_manager.create_event(
                guild_id=self.test_guild_id,
                event_name="Simple Event",
                description="Simple test event",
                category="Simple",
                event_date=datetime.now() + timedelta(days=2),
                created_by_id=self.test_officer_id
            )
            
            simple_event = await self.db_manager.get_event_by_id(simple_event_id)
            assert simple_event['location'] is None, "Location should be None"
            assert simple_event['max_attendees'] is None, "Max attendees should be None"
            print(f"  ✅ Simple event created with ID: {simple_event_id}")
            
            return event_id, simple_event_id
            
        except Exception as e:
            print(f"  ❌ Event creation test failed: {e}")
            raise
    
    async def test_event_invitations(self, event_id):
        """Test event invitation system"""
        print("\n📧 Testing Event Invitations...")
        
        try:
            # Test user invitation
            success = await self.db_manager.invite_user_to_event(
                event_id=event_id,
                guild_id=self.test_guild_id,
                user_id=self.test_user_id,
                invited_by_id=self.test_officer_id,
                invitation_method="direct_invite"
            )
            
            assert success is True, "User invitation should succeed"
            print("  ✅ User invited successfully")
            
            # Test role invitation
            role_success = await self.db_manager.invite_user_to_event(
                event_id=event_id,
                guild_id=self.test_guild_id,
                user_id=self.test_officer_id,
                invited_by_id=self.test_officer_id,
                invitation_method="role_invite",
                role_id=self.test_role_id
            )
            
            assert role_success is True, "Role invitation should succeed"
            print("  ✅ Role invitation successful")
            
            # Test duplicate invitation
            duplicate = await self.db_manager.invite_user_to_event(
                event_id=event_id,
                guild_id=self.test_guild_id,
                user_id=self.test_user_id,
                invited_by_id=self.test_officer_id,
                invitation_method="direct_invite"
            )
            
            assert duplicate is False, "Duplicate invitation should fail"
            print("  ✅ Duplicate invitation properly rejected")
            
            # Test retrieving invitations
            invitations = await self.db_manager.get_event_invitations(event_id)
            assert len(invitations) == 2, "Should have 2 invitations"
            print(f"  ✅ Retrieved {len(invitations)} invitations")
            
        except Exception as e:
            print(f"  ❌ Event invitations test failed: {e}")
            raise
    
    async def test_rsvp_system(self, event_id):
        """Test RSVP functionality"""
        print("\n📋 Testing RSVP System...")
        
        try:
            # Test RSVP responses
            responses = [
                (self.test_user_id, "yes", "Looking forward to it!"),
                (self.test_officer_id, "maybe", "Depends on my schedule"),
            ]
            
            for user_id, response, notes in responses:
                success = await self.db_manager.record_rsvp(
                    event_id=event_id,
                    guild_id=self.test_guild_id,
                    user_id=user_id,
                    response=response,
                    notes=notes
                )
                
                assert success is True, f"RSVP should succeed for user {user_id}"
                print(f"  ✅ RSVP recorded for user {user_id}: {response}")
            
            # Test updating RSVP
            update_success = await self.db_manager.record_rsvp(
                event_id=event_id,
                guild_id=self.test_guild_id,
                user_id=self.test_user_id,
                response="no",
                notes="Changed my mind"
            )
            
            assert update_success is True, "RSVP update should succeed"
            print("  ✅ RSVP updated successfully")
            
            # Test retrieving RSVPs
            rsvps = await self.db_manager.get_event_rsvps(event_id)
            assert 'yes' in rsvps and 'no' in rsvps and 'maybe' in rsvps, "All response types should exist"
            assert len(rsvps['no']) == 1, "Should have 1 'no' response"
            assert len(rsvps['maybe']) == 1, "Should have 1 'maybe' response"
            assert len(rsvps['yes']) == 0, "Should have 0 'yes' responses after update"
            print("  ✅ RSVPs retrieved and validated")
            
            # Test getting specific user RSVP
            user_rsvp = await self.db_manager.get_user_rsvp(event_id, self.test_user_id)
            assert user_rsvp == "no", "User RSVP should be 'no' after update"
            print("  ✅ Individual user RSVP retrieved")
            
        except Exception as e:
            print(f"  ❌ RSVP system test failed: {e}")
            raise
    
    async def test_event_categories(self):
        """Test event category management"""
        print("\n📂 Testing Event Categories...")
        
        try:
            # Create test categories
            categories = [
                ("General", "General purpose events", "#5865F2", "🎉"),
                ("Meeting", "Regular meetings", "#FF6B6B", "📋"),
                ("Training", "Training sessions", "#4ECDC4", "🎓"),
            ]
            
            category_ids = []
            for name, desc, color, emoji in categories:
                cat_id = await self.db_manager.create_event_category(
                    guild_id=self.test_guild_id,
                    category_name=name,
                    description=desc,
                    color_hex=color,
                    emoji=emoji
                )
                category_ids.append(cat_id)
                print(f"  ✅ Category '{name}' created with ID: {cat_id}")
            
            # Retrieve categories
            retrieved_categories = await self.db_manager.get_event_categories(self.test_guild_id)
            assert len(retrieved_categories) == 3, "Should have 3 categories"
            
            for category in retrieved_categories:
                assert category['is_active'] == 1 or category['is_active'] is True, "Categories should be active"
                print(f"  ✅ Category '{category['category_name']}' validated")
            
        except Exception as e:
            print(f"  ❌ Event categories test failed: {e}")
            raise
    
    async def test_event_reminders(self, event_id):
        """Test event reminder system"""
        print("\n⏰ Testing Event Reminders...")
        
        try:
            # Create an event that needs reminders (in the past for testing)
            past_event_id = await self.db_manager.create_event(
                guild_id=self.test_guild_id,
                event_name="Reminder Test Event",
                description="Test reminder functionality",
                category="Testing",
                event_date=datetime.now() + timedelta(hours=1),  # 1 hour from now
                created_by_id=self.test_officer_id,
                reminder_hours_before=2  # Should trigger reminder
            )
            
            # Check for events needing reminders
            events_needing_reminders = await self.db_manager.get_events_needing_reminders()
            
            # Find our test event in the results
            test_event_found = any(
                event['id'] == past_event_id for event in events_needing_reminders
            )
            
            assert test_event_found, "Test event should need reminder"
            print("  ✅ Event correctly identified as needing reminder")
            
            # Mark reminder as sent
            await self.db_manager.mark_reminder_sent(past_event_id)
            
            # Verify reminder is marked as sent
            updated_event = await self.db_manager.get_event_by_id(past_event_id)
            assert updated_event['reminder_sent'] == 1 or updated_event['reminder_sent'] is True, "Reminder should be marked as sent"
            print("  ✅ Reminder marked as sent")
            
            # Check that event no longer needs reminder
            events_after_marking = await self.db_manager.get_events_needing_reminders()
            test_event_still_found = any(
                event['id'] == past_event_id for event in events_after_marking
            )
            
            assert not test_event_still_found, "Event should not need reminder after marking"
            print("  ✅ Event no longer needs reminder after marking sent")
            
        except Exception as e:
            print(f"  ❌ Event reminders test failed: {e}")
            raise
    
    async def test_event_analytics(self, event_id):
        """Test event analytics functionality"""
        print("\n📊 Testing Event Analytics...")
        
        try:
            # Get analytics for the guild
            analytics = await self.db_manager.get_event_analytics(
                guild_id=self.test_guild_id,
                days=30
            )
            
            # Validate analytics structure
            expected_keys = [
                'period_days', 'total_events', 'total_invitations', 'total_responses',
                'response_breakdown', 'response_rate', 'attendance_rate', 
                'category_stats', 'events'
            ]
            
            for key in expected_keys:
                assert key in analytics, f"Analytics should contain '{key}'"
            
            # Validate response breakdown structure
            breakdown = analytics['response_breakdown']
            for response_type in ['yes', 'no', 'maybe']:
                assert response_type in breakdown, f"Breakdown should contain '{response_type}'"
            
            # Check that we have our test events
            assert analytics['total_events'] >= 2, "Should have at least 2 test events"
            assert analytics['total_responses'] >= 2, "Should have at least 2 responses"
            
            print(f"  ✅ Analytics retrieved: {analytics['total_events']} events, {analytics['total_responses']} responses")
            print(f"  ✅ Response rate: {analytics['response_rate']}%, Attendance rate: {analytics['attendance_rate']}%")
            
            # Test category breakdown
            assert len(analytics['category_stats']) > 0, "Should have category statistics"
            print(f"  ✅ Category breakdown: {len(analytics['category_stats'])} categories")
            
        except Exception as e:
            print(f"  ❌ Event analytics test failed: {e}")
            raise
    
    async def test_active_events_listing(self):
        """Test listing active events"""
        print("\n📋 Testing Active Events Listing...")
        
        try:
            # Get all active events
            active_events = await self.db_manager.get_active_events(self.test_guild_id)
            
            # Should have our test events
            assert len(active_events) >= 2, "Should have at least 2 active events"
            
            # Validate event structure
            for event in active_events:
                assert 'id' in event, "Event should have ID"
                assert 'event_name' in event, "Event should have name"
                assert 'event_date' in event, "Event should have date"
                assert 'category' in event, "Event should have category"
                assert 'is_active' in event, "Event should have active status"
                assert event['is_active'] == 1 or event['is_active'] is True, "Event should be active"
                
                # Check RSVP counts
                assert 'yes_count' in event, "Event should have yes count"
                assert 'no_count' in event, "Event should have no count"
                assert 'maybe_count' in event, "Event should have maybe count"
            
            print(f"  ✅ Retrieved {len(active_events)} active events")
            
            # Test date range filtering
            start_date = datetime.now()
            end_date = datetime.now() + timedelta(days=30)
            
            date_filtered_events = await self.db_manager.get_events_by_date_range(
                guild_id=self.test_guild_id,
                start_date=start_date,
                end_date=end_date
            )
            
            assert len(date_filtered_events) >= 1, "Should have events in date range"
            print(f"  ✅ Date range filtering returned {len(date_filtered_events)} events")
            
        except Exception as e:
            print(f"  ❌ Active events listing test failed: {e}")
            raise
    
    async def test_dm_tracking(self, event_id):
        """Test DM invitation tracking"""
        print("\n💬 Testing DM Tracking...")
        
        try:
            # Mark DM as sent for user
            await self.db_manager.mark_dm_sent(event_id, self.test_user_id)
            print("  ✅ DM marked as sent")
            
            # Verify DM status in invitations
            invitations = await self.db_manager.get_event_invitations(event_id)
            
            user_invitation = None
            for invitation in invitations:
                if invitation['user_id'] == self.test_user_id:
                    user_invitation = invitation
                    break
            
            assert user_invitation is not None, "User invitation should exist"
            assert user_invitation['dm_sent'] == 1 or user_invitation['dm_sent'] is True, "DM should be marked as sent"
            print("  ✅ DM status verified in invitations")
            
        except Exception as e:
            print(f"  ❌ DM tracking test failed: {e}")
            raise
    
    async def test_comprehensive_workflow(self):
        """Test a complete event management workflow"""
        print("\n🔄 Testing Comprehensive Workflow...")
        
        try:
            # 1. Create event
            event_id = await self.db_manager.create_event(
                guild_id=self.test_guild_id,
                event_name="Comprehensive Test Event",
                description="Full workflow test",
                category="Integration",
                event_date=datetime.now() + timedelta(days=3),
                location="Integration Test Location",
                max_attendees=25,
                created_by_id=self.test_officer_id,
                reminder_hours_before=48
            )
            print(f"  ✅ Step 1: Event created (ID: {event_id})")
            
            # 2. Invite users
            await self.db_manager.invite_user_to_event(
                event_id, self.test_guild_id, self.test_user_id, 
                self.test_officer_id, "direct_invite"
            )
            await self.db_manager.invite_user_to_event(
                event_id, self.test_guild_id, self.test_officer_id,
                self.test_officer_id, "self_invite"
            )
            print("  ✅ Step 2: Users invited")
            
            # 3. Record RSVPs
            await self.db_manager.record_rsvp(
                event_id, self.test_guild_id, self.test_user_id, "yes", "Excited!"
            )
            await self.db_manager.record_rsvp(
                event_id, self.test_guild_id, self.test_officer_id, "yes", "Will attend"
            )
            print("  ✅ Step 3: RSVPs recorded")
            
            # 4. Send DM notifications
            await self.db_manager.mark_dm_sent(event_id, self.test_user_id)
            await self.db_manager.mark_dm_sent(event_id, self.test_officer_id)
            print("  ✅ Step 4: DM notifications sent")
            
            # 5. Get comprehensive event details
            event_details = await self.db_manager.get_event_by_id(event_id)
            rsvps = await self.db_manager.get_event_rsvps(event_id)
            invitations = await self.db_manager.get_event_invitations(event_id)
            
            # Validate complete workflow
            assert event_details is not None, "Event should exist"
            assert len(rsvps['yes']) == 2, "Should have 2 'yes' responses"
            assert len(invitations) == 2, "Should have 2 invitations"
            assert all(inv['dm_sent'] == 1 or inv['dm_sent'] is True for inv in invitations), "All DMs should be sent"
            
            print("  ✅ Step 5: Comprehensive validation successful")
            print(f"  📊 Final stats: 2 invitations, 2 yes RSVPs, all DMs sent")
            
        except Exception as e:
            print(f"  ❌ Comprehensive workflow test failed: {e}")
            raise
    
    async def run_all_tests(self):
        """Run all event management tests"""
        print("🚀 Starting Event Management System Tests")
        print("=" * 50)
        
        try:
            await self.setup()
            
            # Core functionality tests
            event_id, simple_event_id = await self.test_event_creation()
            await self.test_event_categories()
            await self.test_event_invitations(event_id)
            await self.test_rsvp_system(event_id)
            await self.test_event_reminders(event_id)
            await self.test_dm_tracking(event_id)
            await self.test_active_events_listing()
            await self.test_event_analytics(event_id)
            
            # Integration test
            await self.test_comprehensive_workflow()
            
            print("\n" + "=" * 50)
            print("🎉 ALL TESTS PASSED! Event Management System is ready!")
            print("=" * 50)
            
            # Summary
            active_events = await self.db_manager.get_active_events(self.test_guild_id)
            analytics = await self.db_manager.get_event_analytics(self.test_guild_id, 30)
            categories = await self.db_manager.get_event_categories(self.test_guild_id)
            
            print(f"\n📈 Test Summary:")
            print(f"  • Created {len(active_events)} events")
            print(f"  • Created {len(categories)} categories")
            print(f"  • Recorded {analytics['total_responses']} RSVP responses")
            print(f"  • Sent {analytics['total_invitations']} invitations")
            print(f"  • Overall response rate: {analytics['response_rate']}%")
            
            return True
            
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            await self.teardown()

async def main():
    """Run the event management tests"""
    tester = EventManagementTester()
    success = await tester.run_all_tests()
    
    if success:
        print("\n✅ Event Management System is fully functional and ready for deployment!")
        return 0
    else:
        print("\n❌ Event Management System has issues that need to be resolved.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
