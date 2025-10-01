#!/usr/bin/env python3
"""
Debug script to check prospect data and member associations
"""

import asyncio
import os
import sys
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.database import DatabaseManager

async def debug_prospects():
    """Debug prospect data in the database"""
    db = DatabaseManager("data/thanatos.db")
    guild_id = 889005510286786601  # Your guild ID
    
    try:
        await db.initialize_database()
        
        print("🔍 Debugging Prospect Data...")
        print("=" * 50)
        
        # Check active prospects
        print("\n📋 Active Prospects from Database:")
        active_prospects = await db.get_active_prospects(guild_id)
        
        if not active_prospects:
            print("   No active prospects found.")
        else:
            for prospect in active_prospects:
                print(f"   • ID: {prospect['id']}")
                print(f"     User ID: {prospect['user_id']}")
                print(f"     Sponsor ID: {prospect['sponsor_id']}")
                print(f"     Prospect Name: {prospect.get('prospect_name', 'NULL')}")
                print(f"     Sponsor Name: {prospect.get('sponsor_name', 'NULL')}")
                print(f"     Status: {prospect['status']}")
                print(f"     Start Date: {prospect['start_date']}")
                print(f"     Strikes: {prospect['strikes']}")
                print()
        
        # Check archived prospects
        print("\n📂 Archived Prospects from Database:")
        archived_prospects = await db.get_archived_prospects(guild_id)
        
        if not archived_prospects:
            print("   No archived prospects found.")
        else:
            for prospect in archived_prospects:
                print(f"   • ID: {prospect['id']}")
                print(f"     User ID: {prospect['user_id']}")
                print(f"     Sponsor ID: {prospect['sponsor_id']}")
                print(f"     Prospect Name: {prospect.get('prospect_name', 'NULL')}")
                print(f"     Sponsor Name: {prospect.get('sponsor_name', 'NULL')}")
                print(f"     Status: {prospect['status']}")
                print(f"     Start Date: {prospect['start_date']}")
                print(f"     End Date: {prospect.get('end_date', 'NULL')}")
                print(f"     Strikes: {prospect['strikes']}")
                print()
        
        # Check if members exist for these prospects
        print("\n👥 Checking Member Records:")
        conn = await db._get_shared_connection()
        cursor = await conn.execute("""
            SELECT user_id, discord_name, discord_username 
            FROM members 
            WHERE guild_id = ?
        """, (guild_id,))
        members = await cursor.fetchall()
        
        print(f"   Found {len(members)} member records:")
        for member in members:
            print(f"   • User ID: {member[0]}, Name: {member[1]}, Username: {member[2]}")
        
        # Check raw prospect records
        print(f"\n📊 Raw Prospect Records:")
        cursor = await conn.execute("""
            SELECT id, guild_id, user_id, sponsor_id, status, start_date 
            FROM prospects 
            WHERE guild_id = ?
        """, (guild_id,))
        raw_prospects = await cursor.fetchall()
        
        print(f"   Found {len(raw_prospects)} prospect records:")
        for prospect in raw_prospects:
            print(f"   • ID: {prospect[0]}, User ID: {prospect[2]}, Sponsor ID: {prospect[3]}, Status: {prospect[4]}")
        
        # Show recommendations
        print("\n💡 Recommendations:")
        if raw_prospects and not active_prospects:
            print("   ❌ Prospects exist but JOIN query returns no results")
            print("   🔧 This suggests missing member records")
            print("   📝 Try adding the prospect again to create member records")
        elif not raw_prospects:
            print("   ℹ️  No prospects exist in database")
            print("   📝 Add a prospect using `/prospect action:Add Prospect`")
        else:
            print("   ✅ Prospect data looks good!")
        
    except Exception as e:
        print(f"❌ Error debugging prospects: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(debug_prospects())