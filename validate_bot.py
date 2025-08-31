#!/usr/bin/env python3
"""
Bot validation script to check for common errors before running
"""

import ast
import os
import sys
import importlib.util
from pathlib import Path

def validate_syntax(file_path):
    """Check if a Python file has valid syntax"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the AST to check for syntax errors
        ast.parse(content, filename=file_path)
        print(f"✅ {file_path} - Syntax OK")
        return True
    except SyntaxError as e:
        print(f"❌ {file_path} - Syntax Error: {e}")
        print(f"   Line {e.lineno}: {e.text.strip() if e.text else 'N/A'}")
        return False
    except Exception as e:
        print(f"❌ {file_path} - Error: {e}")
        return False

def check_required_files():
    """Check if all required files exist"""
    required_files = [
        'main.py',
        'config.json',
        'requirements.txt',
        'utils/database.py',
        'utils/time_parser.py',
        'utils/__init__.py',
        'cogs/loa_system.py',
        'cogs/membership.py',
        'cogs/contributions.py',
        'cogs/configuration.py',
        'cogs/backup.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Missing required files:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return False
    else:
        print("✅ All required files present")
        return True

def check_imports():
    """Check if all required packages can be imported"""
    required_packages = [
        'discord',
        'aiosqlite',
        'asyncio',
        'logging',
        'json',
        'datetime',
        'os',
        'io',
        'zipfile'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"✅ {package} - Import OK")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} - Import Failed")
    
    if missing_packages:
        print("\n❌ Missing packages. Install with:")
        print("pip install -r requirements.txt")
        return False
    
    return True

def check_config():
    """Check if config.json is properly formatted"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        required_keys = ['token', 'database_path']
        missing_keys = [key for key in required_keys if key not in config]
        
        if missing_keys:
            print(f"❌ config.json missing keys: {missing_keys}")
            return False
        
        if config['token'] == 'YOUR_BOT_TOKEN_HERE':
            print("⚠️  config.json still has placeholder token")
            return False
        
        print("✅ config.json - Format OK")
        return True
    except Exception as e:
        print(f"❌ config.json - Error: {e}")
        return False

def main():
    """Run all validation checks"""
    print("🤖 Thanatos Bot Validation")
    print("=" * 50)
    
    checks_passed = 0
    total_checks = 0
    
    # Check required files
    total_checks += 1
    if check_required_files():
        checks_passed += 1
    
    print()
    
    # Check Python syntax for all Python files
    python_files = [
        'main.py',
        'utils/database.py',
        'utils/time_parser.py', 
        'cogs/loa_system.py',
        'cogs/membership.py',
        'cogs/contributions.py',
        'cogs/configuration.py',
        'cogs/backup.py'
    ]
    
    syntax_ok = True
    for file_path in python_files:
        if os.path.exists(file_path):
            total_checks += 1
            if validate_syntax(file_path):
                checks_passed += 1
            else:
                syntax_ok = False
    
    print()
    
    # Check config
    total_checks += 1
    if check_config():
        checks_passed += 1
    
    print()
    
    # Check imports
    total_checks += 1
    if check_imports():
        checks_passed += 1
    
    print()
    print("=" * 50)
    print(f"Validation Results: {checks_passed}/{total_checks} checks passed")
    
    if checks_passed == total_checks:
        print("🎉 All checks passed! Bot should be ready to run.")
        return True
    else:
        print("❌ Some checks failed. Please fix the issues before running the bot.")
        return False

if __name__ == '__main__':
    import json
    success = main()
    sys.exit(0 if success else 1)
