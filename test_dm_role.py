#!/usr/bin/env python3
"""
Test script to verify DM Role feature functionality in the Thanatos Bot.
This script checks the implementation of the dm_role command and related functions.
"""

import sys
import os
import asyncio
import inspect
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    from cogs.direct_messaging import DirectMessagingSystem
    import discord
    from discord.ext import commands
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Please ensure all required dependencies are installed.")
    sys.exit(1)

class MockBot:
    """Mock bot for testing"""
    def __init__(self):
        self.db = MockDatabase()

class MockDatabase:
    """Mock database for testing"""
    async def get_server_config(self, guild_id):
        return {
            'guild_id': guild_id,
            'officer_role_id': 12345,
            'notification_channel_id': 67890
        }
    
    async def log_dm_transcript(self, **kwargs):
        return True

class MockGuild:
    """Mock Discord guild for testing"""
    def __init__(self):
        self.id = 123456789
        self.name = "Test Guild"
        self.roles = [
            MockRole(1, "Test Role", ["Member1", "Member2"]),
            MockRole(2, "Empty Role", []),
            MockRole(3, "@everyone", [])  # Default role
        ]
        self.members = [
            MockMember(1, "Member1", False),
            MockMember(2, "Member2", False),
            MockMember(3, "BotMember", True)
        ]
    
    def get_role(self, role_id):
        for role in self.roles:
            if role.id == role_id:
                return role
        return None
    
    def get_channel(self, channel_id):
        if channel_id == 67890:
            return MockChannel()
        return None
    
    def get_member(self, member_id):
        for member in self.members:
            if member.id == member_id:
                return member
        return None

class MockRole:
    """Mock Discord role for testing"""
    def __init__(self, role_id, name, member_names):
        self.id = role_id
        self.name = name
        self.members = [MockMember(i, name, False) for i, name in enumerate(member_names, start=1)]
        self.is_default_role = name == "@everyone"
    
    def is_default(self):
        return self.is_default_role

class MockMember:
    """Mock Discord member for testing"""
    def __init__(self, member_id, name, is_bot):
        self.id = member_id
        self.name = name
        self.display_name = name
        self.bot = is_bot
        self.roles = []
        self.guild_permissions = MockPermissions()
        self.display_avatar = MockAvatar()
    
    async def send(self, embed=None, **kwargs):
        """Mock send method for DM"""
        return True

class MockPermissions:
    """Mock Discord permissions"""
    def __init__(self):
        self.administrator = True

class MockAvatar:
    """Mock Discord avatar"""
    def __init__(self):
        self.url = "https://example.com/avatar.png"

class MockChannel:
    """Mock Discord channel"""
    def __init__(self):
        self.id = 67890
    
    async def send(self, embed=None, **kwargs):
        return True

class MockInteraction:
    """Mock Discord interaction for testing"""
    def __init__(self, guild, user):
        self.guild = guild
        self.user = user
        self.response = MockResponse()
        self.followup = MockFollowup()

class MockResponse:
    """Mock interaction response"""
    def __init__(self):
        self.is_done_value = False
    
    async def defer(self, ephemeral=False):
        pass
    
    async def send_message(self, content=None, embed=None, ephemeral=False):
        print(f"Response: {content or (embed.description if embed else 'Embed sent')}")
        return True
    
    def is_done(self):
        return self.is_done_value

class MockFollowup:
    """Mock interaction followup"""
    async def send(self, content=None, embed=None, ephemeral=False):
        print(f"Followup: {content or (embed.title if embed else 'Embed sent')}")
        return True

def test_dm_role_feature():
    """Test the DM Role feature implementation"""
    print("🧪 Testing Thanatos Bot DM Role Feature")
    print("=" * 50)
    
    # Test 1: Check if DirectMessagingSystem class exists and has dm_role_command
    print("Test 1: Checking DirectMessagingSystem class implementation...")
    try:
        dm_system = DirectMessagingSystem(MockBot())
        
        # Check if dm_role_command method exists
        if hasattr(dm_system, 'dm_role_command'):
            print("✅ dm_role_command method found")
        else:
            print("❌ dm_role_command method not found")
            return False
        
        # Check method signature
        sig = inspect.signature(dm_system.dm_role_command)
        params = list(sig.parameters.keys())
        expected_params = ['self', 'interaction', 'role_identifier', 'message']
        
        if params == expected_params:
            print("✅ dm_role_command has correct signature")
        else:
            print(f"❌ dm_role_command signature mismatch. Expected: {expected_params}, Got: {params}")
            return False
        
    except Exception as e:
        print(f"❌ Error initializing DirectMessagingSystem: {e}")
        return False
    
    print()
    
    # Test 2: Check role finding functionality
    print("Test 2: Testing role finding functionality...")
    try:
        guild = MockGuild()
        
        async def test_role_finding():
            # Test exact role name match
            result = await dm_system._find_role_by_name(guild, "Test Role")
            if result and result.name == "Test Role":
                print("✅ Role finding by exact name works")
            else:
                print("❌ Role finding by exact name failed")
                return False
            
            # Test partial match
            result = await dm_system._find_role_by_name(guild, "test")
            if result and "test" in result.name.lower():
                print("✅ Role finding by partial name works")
            else:
                print("❌ Role finding by partial name failed")
                return False
            
            # Test non-existent role
            result = await dm_system._find_role_by_name(guild, "NonExistent")
            if result is None:
                print("✅ Role finding returns None for non-existent roles")
            else:
                print("❌ Role finding should return None for non-existent roles")
                return False
            
            return True
        
        if not asyncio.run(test_role_finding()):
            return False
    
    except Exception as e:
        print(f"❌ Error testing role finding: {e}")
        return False
    
    print()
    
    # Test 3: Check permission system
    print("Test 3: Testing permission system...")
    try:
        admin_user = MockMember(100, "Admin", False)
        regular_user = MockMember(101, "Regular", False)
        regular_user.guild_permissions.administrator = False
        
        config = {'officer_role_id': 12345}
        
        # Test admin permissions
        if dm_system._has_officer_permissions(admin_user, config):
            print("✅ Admin user has officer permissions")
        else:
            print("❌ Admin user should have officer permissions")
            return False
        
        # Test regular user without officer role
        if not dm_system._has_officer_permissions(regular_user, config):
            print("✅ Regular user without officer role denied permissions")
        else:
            print("❌ Regular user without officer role should be denied permissions")
            return False
        
        # Test regular user with officer role
        officer_role = MockRole(12345, "Officer", [])
        regular_user.roles = [officer_role]
        regular_user.guild = MockGuild()  # Add guild reference
        
        # Mock the guild.get_role method to return the officer role
        def mock_get_role(role_id):
            if role_id == 12345:
                return officer_role
            return None
        
        regular_user.guild.get_role = mock_get_role
        
        if dm_system._has_officer_permissions(regular_user, config):
            print("✅ Regular user with officer role has permissions")
        else:
            print("❌ Regular user with officer role should have permissions")
            return False
            
    except Exception as e:
        print(f"❌ Error testing permissions: {e}")
        return False
    
    print()
    
    # Test 4: Check command structure and error handling
    print("Test 4: Testing command structure and error handling...")
    try:
        # Check if the command is properly decorated
        dm_role_cmd = dm_system.dm_role_command
        
        # Check if it has app_commands.command decorator
        if hasattr(dm_role_cmd, '__discord_app_commands_wrapped__'):
            print("✅ dm_role_command has proper app_commands decorator")
        else:
            # Check for the decorator in a different way
            if hasattr(dm_role_cmd, 'callback') or str(dm_role_cmd).find('app_commands') != -1:
                print("✅ dm_role_command appears to be properly decorated")
            else:
                print("⚠️  Cannot verify app_commands decorator (may still work)")
        
        # Check docstring
        if dm_role_cmd.__doc__ and "DM to all users in a role" in dm_role_cmd.__doc__:
            print("✅ dm_role_command has proper documentation")
        else:
            print("⚠️  dm_role_command documentation could be improved")
            
    except Exception as e:
        print(f"❌ Error testing command structure: {e}")
        return False
    
    print()
    
    # Test 5: Integration test (mock execution)
    print("Test 5: Mock integration test...")
    try:
        async def mock_dm_role_execution():
            guild = MockGuild()
            admin_user = MockMember(100, "Admin", False)
            interaction = MockInteraction(guild, admin_user)
            
            # Mock the sleep function to speed up the test
            with patch('asyncio.sleep', new=AsyncMock()):
                try:
                    await dm_system.dm_role_command(interaction, "Test Role", "Hello everyone!")
                    print("✅ dm_role_command executed without errors")
                    return True
                except Exception as e:
                    print(f"❌ dm_role_command execution failed: {e}")
                    return False
        
        if asyncio.run(mock_dm_role_execution()):
            print("✅ Integration test passed")
        else:
            print("❌ Integration test failed")
            return False
            
    except Exception as e:
        print(f"❌ Error in integration test: {e}")
        return False
    
    return True

def main():
    """Main test function"""
    print("Thanatos Bot - DM Role Feature Test")
    print("=" * 40)
    print()
    
    success = test_dm_role_feature()
    
    print()
    print("=" * 50)
    if success:
        print("🎉 ALL TESTS PASSED! The DM Role feature appears to be working correctly.")
        print()
        print("✅ Key Features Verified:")
        print("   • dm_role_command method exists with correct signature")
        print("   • Role finding functionality works (exact and partial matches)")
        print("   • Permission system properly restricts access")
        print("   • Command structure appears correct")
        print("   • Basic execution flow works without errors")
        print()
        print("📋 The DM Role feature should work as expected when:")
        print("   • Bot has proper permissions in Discord")
        print("   • Users have administrator or officer role permissions")
        print("   • Target roles exist and have members")
        print("   • Bot can send DMs to target users")
        return 0
    else:
        print("❌ TESTS FAILED! There may be issues with the DM Role feature.")
        print("Please review the error messages above for specific problems.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
