#!/usr/bin/env python3
"""
Debug Script for Thanatos Bot
Tests bot initialization and cog loading without connecting to Discord
"""

import asyncio
import logging
import sys
import traceback
from pathlib import Path
import json
import os

# Setup detailed logging for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def test_imports():
    """Test all required imports"""
    print("🔍 Testing imports...")
    
    try:
        import discord
        print(f"✅ Discord.py: {discord.__version__}")
    except ImportError as e:
        print(f"❌ Discord.py import failed: {e}")
        return False
    
    try:
        from utils.database import DatabaseManager
        print("✅ DatabaseManager imported")
    except ImportError as e:
        print(f"❌ DatabaseManager import failed: {e}")
        return False
    
    try:
        from utils.time_parser import TimeParser
        print("✅ TimeParser imported")
    except ImportError as e:
        print(f"❌ TimeParser import failed: {e}")
        return False
    
    try:
        from utils.loa_notifications import LOANotificationManager
        print("✅ LOANotificationManager imported")
    except ImportError as e:
        print(f"❌ LOANotificationManager import failed: {e}")
        return False
    
    try:
        from utils.precise_reminder_system import PreciseReminderSystem
        print("✅ PreciseReminderSystem imported")
    except ImportError as e:
        print(f"❌ PreciseReminderSystem import failed: {e}")
        return False
    
    return True

async def test_cog_imports():
    """Test importing all cogs"""
    print("\n🔍 Testing cog imports...")
    
    cogs_to_test = [
        'cogs.loa_system',
        'cogs.membership', 
        'cogs.contributions',
        'cogs.configuration',
        'cogs.backup',
        'cogs.direct_messaging',
        'cogs.database_management',
        'cogs.enhanced_menu_system',
        'cogs.audit_logs',
        'cogs.events',
        'cogs.event_notepad',
        'cogs.dues_tracking',
        'cogs.prospect_management',
        'cogs.prospect_tasks',
        'cogs.prospect_notes',
        'cogs.prospect_voting',
        'cogs.prospect_dashboard',
        'cogs.prospect_notifications'
    ]
    
    failed_cogs = []
    
    for cog_name in cogs_to_test:
        try:
            __import__(cog_name)
            print(f"✅ {cog_name}")
        except ImportError as e:
            print(f"❌ {cog_name}: {e}")
            failed_cogs.append(cog_name)
        except Exception as e:
            print(f"⚠️ {cog_name}: {type(e).__name__}: {e}")
            failed_cogs.append(cog_name)
    
    return failed_cogs

async def test_database_init():
    """Test database initialization"""
    print("\n🔍 Testing database initialization...")
    
    try:
        from utils.database import DatabaseManager
        
        # Test with the actual database path from config
        db = DatabaseManager("data/thanatos_test.db")
        await db.initialize_database()
        print("✅ Database initialization successful")
        
        # Test guild initialization
        await db.initialize_guild(123456789)  # Test guild ID
        print("✅ Guild initialization successful")
        
        await db.close()
        
        # Clean up test database
        if os.path.exists("data/thanatos_test.db"):
            os.remove("data/thanatos_test.db")
        
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        traceback.print_exc()
        return False

async def test_bot_class():
    """Test bot class initialization without connecting"""
    print("\n🔍 Testing bot class initialization...")
    
    try:
        from main import ThanatosBot
        
        bot = ThanatosBot()
        print("✅ Bot class initialized")
        
        # Test bot properties
        print(f"✅ Bot owners: {bot.bot_owners}")
        print(f"✅ Database manager: {type(bot.db).__name__}")
        print(f"✅ Time parser: {type(bot.time_parser).__name__}")
        
        return True
        
    except Exception as e:
        print(f"❌ Bot class initialization failed: {e}")
        traceback.print_exc()
        return False

async def test_config():
    """Test configuration file"""
    print("\n🔍 Testing configuration...")
    
    try:
        if not os.path.exists('config.json'):
            print("❌ config.json not found")
            return False
        
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        if 'token' not in config:
            print("❌ Token not found in config")
            return False
        
        if config['token'] == "YOUR_BOT_TOKEN_HERE":
            print("❌ Bot token not configured")
            return False
        
        if 'database_path' not in config:
            print("❌ Database path not found in config")
            return False
        
        print("✅ Configuration file valid")
        
        # Check if database directory exists
        db_path = Path(config['database_path'])
        if not db_path.parent.exists():
            print(f"⚠️ Database directory doesn't exist, creating: {db_path.parent}")
            db_path.parent.mkdir(parents=True, exist_ok=True)
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

async def run_debug():
    """Run all debug tests"""
    print("🚀 Starting Thanatos Bot Debug Session")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 5
    
    # Test imports
    if await test_imports():
        tests_passed += 1
    
    # Test configuration
    if await test_config():
        tests_passed += 1
    
    # Test cog imports
    failed_cogs = await test_cog_imports()
    if not failed_cogs:
        tests_passed += 1
    
    # Test database
    if await test_database_init():
        tests_passed += 1
    
    # Test bot class
    if await test_bot_class():
        tests_passed += 1
    
    print("\n" + "=" * 50)
    print(f"🎯 Debug Summary: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("✅ All tests passed! Bot should start successfully.")
    else:
        print("❌ Some tests failed. Check the errors above.")
        
        if failed_cogs:
            print(f"\n⚠️ Failed cogs: {', '.join(failed_cogs)}")
            print("These cogs may need to be removed from main.py or fixed.")
    
    print("\n🔧 To start the bot normally, run: python main.py")

if __name__ == "__main__":
    asyncio.run(run_debug())
