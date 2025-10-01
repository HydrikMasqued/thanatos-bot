#!/usr/bin/env python3
"""
Installation script for dateutil package required for enhanced datetime parsing
"""

import subprocess
import sys
import os

def install_package(package_name):
    """Install a package using pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        print(f"✅ Successfully installed {package_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package_name}: {e}")
        return False

def main():
    """Main installation function"""
    print("🚀 Installing enhanced datetime parsing dependencies...")
    print("=" * 50)
    
    # Required packages for enhanced datetime parsing
    packages = [
        "python-dateutil",  # For natural language datetime parsing
    ]
    
    success_count = 0
    
    for package in packages:
        print(f"\n📦 Installing {package}...")
        if install_package(package):
            success_count += 1
    
    print("\n" + "=" * 50)
    print(f"✨ Installation complete!")
    print(f"📊 Successfully installed {success_count}/{len(packages)} packages")
    
    if success_count == len(packages):
        print("🎉 All dependencies installed successfully!")
        print("🔧 The enhanced dues management system is now ready to use.")
        print("\n💡 Features enabled:")
        print("  • Natural language date parsing (e.g., 'next friday 6pm')")
        print("  • Relative date parsing (e.g., '2 weeks', '1 month')")
        print("  • Enhanced datetime formats")
        print("  • Fancy UI components with member dropdowns")
        print("  • Period cancellation functionality")
    else:
        print("⚠️  Some dependencies failed to install.")
        print("🔄 You may need to install them manually or run this script as administrator.")

if __name__ == "__main__":
    main()