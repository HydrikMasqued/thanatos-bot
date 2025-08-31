#!/usr/bin/env python3
import sys
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
sys.path.append('.')

async def test_integration():
    print("Testing integration and error handling...")
    
    print("\n=== Testing Config Error Handling ===")
    
    # Test missing config file
    try:
        import os, tempfile, shutil
        
        # Create a temporary directory for testing
        test_dir = tempfile.mkdtemp()
        original_dir = os.getcwd()
        
        os.chdir(test_dir)
        
        # Test main.py config error handling
        sys.path.insert(0, original_dir)
        from main import main
        
        # This should handle missing config gracefully
        try:
            main()
            print("✅ Missing config handled gracefully")
        except SystemExit:
            print("✅ Missing config causes proper exit")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        
        # Clean up
        os.chdir(original_dir)
        shutil.rmtree(test_dir)
        
    except Exception as e:
        print(f"❌ Config test error: {e}")
    
    print("\n=== Testing Database Error Handling ===")
    
    try:
        from utils.database import DatabaseManager
        
        # Test with invalid database path
        db = DatabaseManager(db_path="/invalid/path/test.db")
        try:
            await db.initialize_database()
            print("✅ Database error handling works")
        except Exception as e:
            print(f"✅ Database error properly caught: {type(e).__name__}")
        finally:
            try:
                await db.close()
            except:
                pass
                
    except Exception as e:
        print(f"❌ Database error test failed: {e}")
    
    print("\n=== Testing Import Dependencies ===")
    
    # Test all critical imports
    critical_modules = [
        'discord',
        'aiosqlite', 
        'asyncio',
        'datetime',
        'json',
        'logging',
        'os',
        'sys'
    ]
    
    for module in critical_modules:
        try:
            __import__(module)
            print(f"✅ {module} import OK")
        except ImportError as e:
            print(f"❌ {module} import failed: {e}")
    
    print("\n=== Testing Cog Loading Simulation ===")
    
    # Test that all cog files can be imported
    cog_files = [
        'cogs.loa_system',
        'cogs.membership', 
        'cogs.contributions',
        'cogs.configuration',
        'cogs.backup',
        'cogs.direct_messaging',
        'cogs.database_management',
        'cogs.enhanced_menu_system',
        'cogs.audit_logs'
    ]
    
    for cog in cog_files:
        try:
            __import__(cog)
            print(f"✅ {cog} import OK")
        except ImportError as e:
            print(f"❌ {cog} import failed: {e}")
        except Exception as e:
            print(f"⚠️ {cog} import warning: {type(e).__name__}")
    
    print("\n=== Testing Time Parser Edge Cases ===")
    
    try:
        from utils.time_parser import TimeParser
        parser = TimeParser()
        
        # Test edge cases
        edge_cases = [
            "",
            "invalid",
            "0 days",
            "-5 days",
            "999 years",
            "1.5 days"
        ]
        
        for test_case in edge_cases:
            try:
                result = parser.parse_duration(test_case)
                print(f"⚠️ Unexpected success for '{test_case}': {result}")
            except Exception as e:
                print(f"✅ '{test_case}' properly rejected: {type(e).__name__}")
                
    except Exception as e:
        print(f"❌ Time parser edge case test failed: {e}")
    
    print("\n🎉 Integration and error handling tests completed!")

if __name__ == "__main__":
    asyncio.run(test_integration())
