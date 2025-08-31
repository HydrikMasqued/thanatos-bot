import discord
import asyncio
import sys
import os

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import bot

async def examine_forums():
    """Examine forum channels and their threads"""
    
    # Target guild ID from your server
    target_guild_id = 889005510286786601
    guild = bot.get_guild(target_guild_id)
    
    if not guild:
        print("Guild not found!")
        return
    
    print(f"Examining guild: {guild.name} (ID: {guild.id})")
    print("=" * 50)
    
    # Forum channel IDs from the contribution system
    forum_ids = {
        1355399894227091517: "Weapons",
        1366601638130880582: "Equipment & Medical", 
        1366605626662322236: "Contraband",
    }
    
    for forum_id, forum_type in forum_ids.items():
        forum_channel = guild.get_channel(forum_id)
        if not forum_channel:
            print(f"❌ {forum_type} forum not found (ID: {forum_id})")
            continue
        
        print(f"\n📋 {forum_type} Forum: {forum_channel.name} (ID: {forum_id})")
        print("-" * 40)
        
        # Get active threads
        active_threads = forum_channel.threads
        if active_threads:
            print(f"📝 Active Threads ({len(active_threads)}):")
            for thread in active_threads:
                print(f"  • {thread.name} (ID: {thread.id})")
        
        # Get archived threads
        archived_threads = []
        async for thread in forum_channel.archived_threads(limit=20):
            archived_threads.append(thread)
        
        if archived_threads:
            print(f"\n📁 Recent Archived Threads ({len(archived_threads)}):")
            for thread in archived_threads[:10]:  # Show first 10
                print(f"  • {thread.name} (ID: {thread.id})")
    
    print("\n" + "=" * 50)
    print("Examination complete!")

# Run the examination
if __name__ == "__main__":
    try:
        asyncio.run(examine_forums())
    except Exception as e:
        print(f"Error: {e}")
