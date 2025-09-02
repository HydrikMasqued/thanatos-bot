import asyncio
import sys
sys.path.append('.')
from utils.database import DatabaseManager
from datetime import datetime

async def check_loas():
    db = DatabaseManager()
    try:
        # Get expired LOAs
        expired_loas = await db.get_expired_loas()
        print(f'Found {len(expired_loas)} expired LOAs:')
        for loa in expired_loas:
            print(f'LOA ID: {loa["id"]}, User: {loa["user_id"]}, End Time: {loa["end_time"]}, Active: {loa["is_active"]}, Expired: {loa["is_expired"]}')
        
        # Get all LOA records to see what's in there
        conn = await db._get_shared_connection()
        cursor = await conn.execute('SELECT * FROM loa_records ORDER BY id DESC LIMIT 10')
        all_loas = await cursor.fetchall()
        print(f'\nAll LOA records (last 10):')
        for loa in all_loas:
            print(f'ID: {loa[0]}, Guild: {loa[1]}, User: {loa[2]}, End: {loa[6]}, Active: {loa[7]}, Expired: {loa[8]}')
            
        # Get active LOAs for all guilds
        print(f'\nActive LOAs:')
        cursor = await conn.execute('SELECT * FROM loa_records WHERE is_active = TRUE AND is_expired = FALSE')
        active_loas = await cursor.fetchall()
        for loa in active_loas:
            print(f'Active LOA - ID: {loa[0]}, Guild: {loa[1]}, User: {loa[2]}, End: {loa[6]}')
            
    finally:
        await db.close()

if __name__ == '__main__':
    asyncio.run(check_loas())
