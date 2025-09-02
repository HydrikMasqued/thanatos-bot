import asyncio
import sys
sys.path.append('.')
from utils.database import DatabaseManager
from datetime import datetime

async def cleanup_orphaned_loas():
    """Clean up LOA records from guilds that no longer exist"""
    db = DatabaseManager()
    try:
        # Valid guild IDs (from the bot logs)
        valid_guild_ids = [889005510286786601, 1396144378271109221]
        
        conn = await db._get_shared_connection()
        
        # Get all LOA records from invalid guilds
        cursor = await conn.execute('''
            SELECT * FROM loa_records 
            WHERE guild_id NOT IN (?, ?)
        ''', (*valid_guild_ids,))
        
        orphaned_loas = await cursor.fetchall()
        print(f'Found {len(orphaned_loas)} orphaned LOA records:')
        
        for loa in orphaned_loas:
            print(f'ID: {loa[0]}, Guild: {loa[1]}, User: {loa[2]}, End: {loa[6]}, Active: {loa[7]}, Expired: {loa[8]}')
        
        if orphaned_loas:
            # Ask for confirmation
            print(f'\nDo you want to delete these {len(orphaned_loas)} orphaned LOA records? (y/n): ', end='')
            confirm = input().strip().lower()
            
            if confirm == 'y':
                # Delete orphaned LOA records
                await conn.execute('''
                    DELETE FROM loa_records 
                    WHERE guild_id NOT IN (?, ?)
                ''', (*valid_guild_ids,))
                
                await db._execute_commit()
                print(f'✅ Deleted {len(orphaned_loas)} orphaned LOA records.')
            else:
                print('❌ Cleanup cancelled.')
        else:
            print('✅ No orphaned LOA records found.')
            
        # Also check for any expired LOAs that should be marked as expired
        print(f'\nChecking for expired LOAs that need to be marked...')
        cursor = await conn.execute('''
            SELECT * FROM loa_records 
            WHERE is_active = TRUE AND is_expired = FALSE 
            AND end_time <= ? AND guild_id IN (?, ?)
        ''', (datetime.now(), *valid_guild_ids))
        
        expired_loas = await cursor.fetchall()
        if expired_loas:
            print(f'Found {len(expired_loas)} expired LOAs to mark:')
            for loa in expired_loas:
                print(f'LOA ID: {loa[0]}, User: {loa[2]}, End: {loa[6]}')
                await db.mark_loa_expired(loa[0])
            print(f'✅ Marked {len(expired_loas)} LOAs as expired.')
        else:
            print('✅ No expired LOAs to mark.')
            
    finally:
        await db.close()

if __name__ == '__main__':
    asyncio.run(cleanup_orphaned_loas())
