#!/usr/bin/env python3
"""
Debug startup script for Thanatos Bot
Runs the enhanced debug version with comprehensive monitoring
"""

import subprocess
import sys
import os
import time
from pathlib import Path
from datetime import datetime

def print_banner():
    """Print startup banner"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    🤖 THANATOS BOT DEBUG MODE                 ║
║                  Enhanced Monitoring & Logging               ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 66)

def check_requirements():
    """Check if all requirements are met"""
    print("🔍 Checking requirements...")
    
    # Check if config exists
    if not Path('config.json').exists():
        print("❌ config.json not found!")
        return False
    
    # Check if logs directory exists
    logs_dir = Path('logs')
    if not logs_dir.exists():
        print("📁 Creating logs directory...")
        logs_dir.mkdir()
    
    # Check if debug_main.py exists
    if not Path('debug_main.py').exists():
        print("❌ debug_main.py not found!")
        return False
    
    print("✅ All requirements met!")
    return True

def start_bot():
    """Start the debug bot"""
    print("🚀 Starting Thanatos Bot in DEBUG MODE...")
    print("📝 All activities will be logged to logs/ directory")
    print("🔍 Use monitor_logs.py for real-time monitoring")
    print("⚠️  This version includes extensive debugging - expect verbose output!")
    print("=" * 66)
    
    try:
        # Start the debug bot
        process = subprocess.Popen(
            [sys.executable, 'debug_main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Print output in real-time
        for line in iter(process.stdout.readline, ''):
            print(line.rstrip())
            
    except KeyboardInterrupt:
        print("\n🛑 Bot shutdown requested by user")
        if 'process' in locals():
            process.terminate()
            process.wait()
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        return False
    
    return True

def main():
    """Main startup function"""
    print_banner()
    
    if not check_requirements():
        print("\n❌ Requirements not met. Please fix the issues above.")
        sys.exit(1)
    
    print("\n🎯 Debug features enabled:")
    print("  • Comprehensive logging (DEBUG level)")
    print("  • Real-time error tracking")
    print("  • Command usage monitoring")
    print("  • Enhanced error handling")
    print("  • Component initialization tracking")
    print("  • Background task monitoring")
    print("  • Database operation logging")
    print("  • User interaction tracking")
    
    print("\n📊 Available monitoring commands:")
    print("  • python monitor_logs.py --monitor    (Real-time log monitoring)")
    print("  • python monitor_logs.py --analyze    (Log analysis)")
    print("  • python monitor_logs.py --tail <file> (Show recent log entries)")
    print("  • !debug_stats                        (Bot statistics in Discord)")
    
    print("\n" + "=" * 66)
    input("Press ENTER to start the bot or Ctrl+C to cancel...")
    
    success = start_bot()
    
    if success:
        print("\n✅ Bot stopped successfully")
    else:
        print("\n❌ Bot encountered an error")
        sys.exit(1)

if __name__ == '__main__':
    main()
