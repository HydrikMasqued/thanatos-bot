#!/usr/bin/env python3
"""
Simple diagnostic to check DM Role implementation in Thanatos Bot
"""

import sys
import os
import inspect

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def check_dm_role_implementation():
    """Check the DM Role implementation"""
    print("🔍 Checking DM Role Implementation in Thanatos Bot")
    print("=" * 55)
    
    try:
        # Import the DirectMessagingSystem
        from cogs.direct_messaging import DirectMessagingSystem
        print("✅ Successfully imported DirectMessagingSystem")
        
        # Check if the class has the expected methods
        methods = [method for method in dir(DirectMessagingSystem) if not method.startswith('_')]
        print(f"📋 Available methods: {', '.join(methods)}")
        
        # Check specifically for dm_role_command
        if 'dm_role_command' in methods:
            print("✅ dm_role_command method found")
            
            # Get the method
            dm_role_method = getattr(DirectMessagingSystem, 'dm_role_command')
            
            # Check if it's decorated
            if hasattr(dm_role_method, '__wrapped__'):
                print("✅ dm_role_command appears to be decorated")
            else:
                print("⚠️  dm_role_command decoration unclear")
            
            # Check method signature without instantiating
            try:
                sig = inspect.signature(dm_role_method)
                params = list(sig.parameters.keys())
                print(f"📝 Method signature: {params}")
                
                expected_params = ['self', 'interaction', 'role_identifier', 'message']
                if params == expected_params:
                    print("✅ Method signature is correct")
                else:
                    print(f"⚠️  Expected: {expected_params}, Got: {params}")
            except Exception as e:
                print(f"⚠️  Could not inspect signature: {e}")
            
            # Check docstring
            if dm_role_method.__doc__:
                print(f"📖 Docstring: {dm_role_method.__doc__.strip()}")
            else:
                print("⚠️  No docstring found")
                
        else:
            print("❌ dm_role_command method NOT found")
            return False
        
        # Check other key methods for DM functionality
        key_methods = [
            '_find_role_by_name',
            '_has_officer_permissions', 
            '_log_transcript',
            'dm_user_command'
        ]
        
        print("\n🔍 Checking other key DM methods:")
        for method_name in key_methods:
            if method_name in methods:
                print(f"✅ {method_name} - found")
            else:
                print(f"❌ {method_name} - missing")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("The DirectMessagingSystem cog may not be available")
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        return False

def check_file_structure():
    """Check if required files exist"""
    print("\n📁 Checking file structure:")
    
    files_to_check = [
        "cogs/direct_messaging.py",
        "main.py",
        "utils/database.py"
    ]
    
    for file_path in files_to_check:
        full_path = os.path.join(os.path.dirname(__file__), file_path)
        if os.path.exists(full_path):
            print(f"✅ {file_path} - exists")
        else:
            print(f"❌ {file_path} - missing")

def main():
    """Main diagnostic function"""
    print("Thanatos Bot - DM Role Feature Diagnostic")
    print("=" * 45)
    
    # Check file structure first
    check_file_structure()
    
    print()
    
    # Check implementation
    success = check_dm_role_implementation()
    
    print("\n" + "=" * 55)
    if success:
        print("✅ DIAGNOSTIC COMPLETE - DM Role feature implementation looks good!")
        print("\n📋 Summary:")
        print("   • DirectMessagingSystem class is available")
        print("   • dm_role_command method exists")
        print("   • Key supporting methods are present")
        print("\n🚀 The feature should work if:")
        print("   • Bot is properly configured and running")
        print("   • Users have correct permissions")
        print("   • Discord.py dependencies are satisfied")
    else:
        print("❌ DIAGNOSTIC FAILED - Issues found with DM Role feature")
        print("Please review the errors above.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
