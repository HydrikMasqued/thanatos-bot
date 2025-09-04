#!/usr/bin/env python3
"""
Bot Startup Diagnostic - Comprehensive Testing
Simulates bot startup to identify issues without connecting to Discord
"""

import sys
import os
import asyncio
import logging
import traceback
from datetime import datetime

# Ensure current directory is in Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class BotDiagnostic:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.successes = []

    def log_success(self, message):
        self.successes.append(message)
        print(f"✅ {message}")

    def log_warning(self, message):
        self.warnings.append(message)
        print(f"⚠️  {message}")

    def log_issue(self, message):
        self.issues.append(message)
        print(f"❌ {message}")

    async def test_imports(self):
        """Test all critical imports"""
        print("\n🔍 Testing Critical Imports...")
        
        # Core Discord.py
        try:
            import discord
            from discord.ext import commands
            self.log_success("Discord.py imports - OK")
        except Exception as e:
            self.log_issue(f"Discord.py imports failed: {e}")

        # Database utilities
        try:
            from utils.database import DatabaseManager
            self.log_success("Database utilities - OK")
        except Exception as e:
            self.log_issue(f"Database utilities failed: {e}")

        # Time utilities
        try:
            from utils.time_parser import TimeParser
            from utils.smart_time_formatter import SmartTimeFormatter
            from utils.advanced_timestamp_parser import AdvancedTimestampParser
            from utils.universal_timestamp import UniversalTimestamp
            self.log_success("Time utilities - OK")
        except Exception as e:
            self.log_issue(f"Time utilities failed: {e}")

        # Notification utilities
        try:
            from utils.loa_notifications import LOANotificationManager
            from utils.precise_reminder_system import PreciseReminderSystem
            self.log_success("Notification utilities - OK")
        except Exception as e:
            self.log_issue(f"Notification utilities failed: {e}")

    async def test_cogs(self):
        """Test all cog imports and basic functionality"""
        print("\n🔍 Testing Cogs...")
        
        cogs = [
            'cogs.loa_system', 
            'cogs.membership', 
            'cogs.contributions', 
            'cogs.configuration', 
            'cogs.direct_messaging', 
            'cogs.database_management', 
            'cogs.audit_logs', 
            'cogs.events', 
            'cogs.event_notepad', 
            'cogs.dues_tracking', 
            'cogs.prospect_core', 
            'cogs.prospect_dashboard', 
            'cogs.prospect_notifications', 
            'cogs.enhanced_menu_system',
            'cogs.timestamp_demo'
        ]

        failed_cogs = []
        
        for cog_name in cogs:
            try:
                # Import the cog module
                module = __import__(cog_name, fromlist=[''])
                
                # Check for setup function
                if hasattr(module, 'setup'):
                    self.log_success(f"{cog_name} - Import and setup function OK")
                else:
                    self.log_warning(f"{cog_name} - Missing setup function")
                    
            except Exception as e:
                self.log_issue(f"{cog_name} - Failed: {e}")
                failed_cogs.append((cog_name, str(e)))

        if not failed_cogs:
            self.log_success("All cogs import successfully")

    async def test_database(self):
        """Test database connectivity and initialization"""
        print("\n🔍 Testing Database...")
        
        try:
            from utils.database import DatabaseManager
            
            # Test database manager creation
            db = DatabaseManager()
            self.log_success("Database manager creation - OK")
            
            # Test database initialization
            await db.initialize_database()
            self.log_success("Database initialization - OK")
            
            # Test basic database operations
            await db.initialize_guild(12345)  # Test guild
            self.log_success("Guild initialization - OK")
            
            # Close database
            await db.close()
            self.log_success("Database connectivity - All OK")
            
        except Exception as e:
            self.log_issue(f"Database testing failed: {e}")
            traceback.print_exc()

    async def test_timestamp_system(self):
        """Test timestamp parsing system"""
        print("\n🔍 Testing Timestamp System...")
        
        try:
            from utils.universal_timestamp import parse_time, validate_time
            
            # Test basic parsing
            test_cases = [
                "today",
                "tomorrow 8pm", 
                "next week",
                "friday afternoon"
            ]
            
            all_passed = True
            for test_case in test_cases:
                result = parse_time(test_case)
                if result:
                    self.log_success(f"Parse '{test_case}' - OK")
                else:
                    self.log_issue(f"Parse '{test_case}' - Failed")
                    all_passed = False
            
            if all_passed:
                self.log_success("Timestamp system - All OK")
            
        except Exception as e:
            self.log_issue(f"Timestamp system failed: {e}")
            traceback.print_exc()

    async def test_config(self):
        """Test configuration files"""
        print("\n🔍 Testing Configuration...")
        
        # Check for config.json
        if os.path.exists('config.json'):
            try:
                import json
                with open('config.json', 'r') as f:
                    config = json.load(f)
                
                if config.get('token') and config['token'] != "YOUR_BOT_TOKEN_HERE":
                    self.log_success("config.json - Token configured")
                else:
                    self.log_issue("config.json - Token not configured (bot won't start)")
                    
                if config.get('database_path'):
                    self.log_success("config.json - Database path configured")
                    
            except Exception as e:
                self.log_issue(f"config.json - Invalid format: {e}")
        else:
            self.log_warning("config.json - File not found (will be created on first run)")

    async def test_file_structure(self):
        """Test file structure and required directories"""
        print("\n🔍 Testing File Structure...")
        
        required_dirs = ['utils', 'cogs', 'data']
        for directory in required_dirs:
            if os.path.exists(directory):
                self.log_success(f"Directory '{directory}' - OK")
            else:
                if directory == 'data':
                    self.log_warning(f"Directory '{directory}' - Missing (will be created)")
                else:
                    self.log_issue(f"Directory '{directory}' - Missing")

        # Check for main.py
        if os.path.exists('main.py'):
            self.log_success("main.py - OK")
        else:
            self.log_issue("main.py - Missing")

    async def test_command_structure(self):
        """Test command structure in cogs"""
        print("\n🔍 Testing Command Structure...")
        
        try:
            # Test enhanced menu system commands
            from cogs.enhanced_menu_system import EnhancedMenuSystem
            self.log_success("Enhanced menu system class - OK")
            
            # Test timestamp demo commands
            from cogs.timestamp_demo import TimestampDemo
            self.log_success("Timestamp demo class - OK")
            
            # Test event system commands
            from cogs.events import EventSystem
            self.log_success("Event system class - OK")
            
            # Test dues tracking commands
            from cogs.dues_tracking import AdvancedDuesTrackingSystem
            self.log_success("Dues tracking system class - OK")
            
        except Exception as e:
            self.log_issue(f"Command structure test failed: {e}")

    async def run_diagnostics(self):
        """Run all diagnostic tests"""
        print("🧪 BOT COMPREHENSIVE DIAGNOSTIC")
        print("=" * 50)
        print(f"Started at: {datetime.now()}")
        
        # Run all tests
        await self.test_file_structure()
        await self.test_config()
        await self.test_imports()
        await self.test_cogs()
        await self.test_database()
        await self.test_timestamp_system()
        await self.test_command_structure()
        
        # Summary
        print("\n" + "=" * 50)
        print("🎯 DIAGNOSTIC RESULTS SUMMARY")
        print("=" * 50)
        
        print(f"✅ Successes: {len(self.successes)}")
        print(f"⚠️  Warnings: {len(self.warnings)}")
        print(f"❌ Issues: {len(self.issues)}")
        
        if self.issues:
            print("\n🚨 CRITICAL ISSUES FOUND:")
            for issue in self.issues:
                print(f"  • {issue}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        print("\n" + "=" * 50)
        
        if not self.issues:
            print("🎉 BOT IS READY FOR DEPLOYMENT!")
            print("✅ All critical systems operational")
        else:
            print("⚠️  BOT HAS ISSUES THAT NEED FIXING")
            print("❌ Fix critical issues before deployment")
        
        print("=" * 50)
        
        return len(self.issues) == 0

async def main():
    """Main diagnostic function"""
    diagnostic = BotDiagnostic()
    success = await diagnostic.run_diagnostics()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
