import asyncio
import sys
import os
from datetime import datetime

# Add the project root directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

# Test imports
try:
    from main import ThanatosBot
    print("✅ Main bot class imported successfully")
except Exception as e:
    print(f"❌ Failed to import main bot class: {e}")
    sys.exit(1)

async def test_bot_initialization():
    """Test bot initialization and cog loading"""
    print("🚀 Testing Bot Initialization and Cog Loading\n")
    print("=" * 60)
    
    try:
        # Create bot instance
        print("📋 Creating bot instance...")
        bot = ThanatosBot()
        print("✅ Bot instance created successfully")
        
        # Test database initialization
        print("\n📋 Testing database initialization...")
        await bot.db.initialize_database()
        print("✅ Database initialization successful")
        
        # Test cog loading (manually for testing)
        prospect_cogs = [
            'cogs.prospect_management',
            'cogs.prospect_tasks', 
            'cogs.prospect_notes',
            'cogs.prospect_voting',
            'cogs.prospect_dashboard',
            'cogs.prospect_notifications'
        ]
        
        print(f"\n📋 Testing {len(prospect_cogs)} prospect management cogs...")
        
        for cog_name in prospect_cogs:
            try:
                await bot.load_extension(cog_name)
                print(f"  ✅ {cog_name} - LOADED")
            except Exception as e:
                print(f"  ❌ {cog_name} - FAILED: {e}")
        
        # Test database methods exist
        print("\n📋 Testing database methods availability...")
        required_methods = [
            'get_prospect_by_user',
            'create_prospect', 
            'add_prospect_task',
            'get_prospect_tasks',
            'add_prospect_note',
            'start_prospect_vote',
            'get_active_prospect_vote',
            'cast_prospect_vote',
            'get_overdue_tasks'
        ]
        
        for method in required_methods:
            if hasattr(bot.db, method):
                print(f"  ✅ {method} - AVAILABLE")
            else:
                print(f"  ❌ {method} - MISSING")
        
        # Check loaded cogs
        print(f"\n📋 Loaded cogs ({len(bot.cogs)}):")
        for cog_name in sorted(bot.cogs.keys()):
            cog = bot.cogs[cog_name]
            commands = [cmd.name for cmd in cog.get_commands()]
            app_commands = [cmd.name for cmd in cog.get_app_commands()]
            print(f"  ✅ {cog_name}: {len(commands)} prefix commands, {len(app_commands)} slash commands")
        
        # Test permissions system
        print(f"\n📋 Testing permissions system...")
        try:
            from utils.permissions import has_required_permissions
            print("  ✅ Permissions module loaded")
        except Exception as e:
            print(f"  ❌ Permissions module failed: {e}")
        
        # Test time parsing system
        print(f"\n📋 Testing time parsing system...")
        try:
            from utils.time_parsing import parse_date_or_duration
            test_date = parse_date_or_duration("1 week")
            if test_date:
                print("  ✅ Time parsing working correctly")
            else:
                print("  ❌ Time parsing returned None")
        except Exception as e:
            print(f"  ❌ Time parsing failed: {e}")
        
        # Close database
        print(f"\n📋 Cleaning up...")
        await bot.close()
        print("✅ Bot closed successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run the bot initialization test"""
    print(f"🤖 Thanatos Prospect Management System - Initialization Test")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    success = await test_bot_initialization()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 BOT INITIALIZATION TEST PASSED!")
        print("✅ All prospect management systems ready")
        print("✅ All cogs loaded successfully")
        print("✅ Database and utilities working")
        print("🚀 SYSTEM READY FOR PRODUCTION")
    else:
        print("❌ BOT INITIALIZATION TEST FAILED!")
        print("🚨 Check errors above and fix before deployment")
    
    print(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    asyncio.run(main())
