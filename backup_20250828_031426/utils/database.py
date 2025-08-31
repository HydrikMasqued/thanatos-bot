import aiosqlite
import json
from datetime import datetime
import os
import asyncio
import logging
from typing import List, Dict, Optional, Any

# Set up logger for this module
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "data/thanatos.db"):
        self.db_path = db_path
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Connection management
        self._connection_lock = asyncio.Lock()
        self._shared_connection = None
        self._max_retries = 5  # Increased from 3
        self._retry_delay = 0.1  # Start with shorter delay
        self._initialized = False
        
        logger.info(f"Database manager initialized with path: {db_path}")
    
    async def close(self):
        """Cleanup database resources"""
        async with self._connection_lock:
            if self._shared_connection:
                try:
                    await self._shared_connection.close()
                    self._shared_connection = None
                    logger.info("Database connection closed")
                except Exception as e:
                    logger.error(f"Error closing database connection: {e}")
    
    async def _get_shared_connection(self):
        """Get or create shared database connection"""
        async with self._connection_lock:
            if self._shared_connection is None:
                try:
                    self._shared_connection = await aiosqlite.connect(
                        self.db_path,
                        timeout=30.0,
                        check_same_thread=False
                    )
                    # Configure SQLite for better concurrency
                    await self._shared_connection.execute('PRAGMA foreign_keys = ON')
                    await self._shared_connection.execute('PRAGMA journal_mode = WAL')
                    await self._shared_connection.execute('PRAGMA synchronous = NORMAL')
                    await self._shared_connection.execute('PRAGMA cache_size = -2000')
                    await self._shared_connection.execute('PRAGMA temp_store = MEMORY')
                    await self._shared_connection.execute('PRAGMA busy_timeout = 30000')
                    logger.info("Shared database connection established")
                except Exception as e:
                    logger.error(f"Failed to establish shared database connection: {e}")
                    self._shared_connection = None
                    raise
            return self._shared_connection
    
    async def _execute_query(self, query, params=None):
        """Execute a query with retry logic and proper connection management"""
        current_delay = self._retry_delay
        for attempt in range(self._max_retries):
            try:
                conn = await self._get_shared_connection()
                cursor = await conn.execute(query, params or ())
                return cursor
            except Exception as e:
                if attempt < self._max_retries - 1:
                    logger.warning(f"Database query attempt {attempt + 1} failed: {e}. Retrying in {current_delay}s...")
                    # Reset connection on error
                    async with self._connection_lock:
                        if self._shared_connection:
                            try:
                                await self._shared_connection.close()
                            except:
                                pass
                            self._shared_connection = None
                    await asyncio.sleep(current_delay)
                    current_delay *= 2
                else:
                    logger.error(f"Failed to execute query after {self._max_retries} attempts: {e}")
                    raise
    
    async def _execute_commit(self):
        """Execute commit with proper connection management"""
        conn = await self._get_shared_connection()
        await conn.commit()
    
    async def initialize_database(self):
        """Initialize all database tables"""
        try:
            logger.info("Initializing database tables")
            conn = await self._get_shared_connection()
            
            # Check if LOA notification columns exist and add them if not
            await self._migrate_loa_notification_columns(conn)
            
            # Migrate dm_user_id to dm_users JSON array
            await self._migrate_dm_users_column(conn)
            
            # Server configurations table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS server_configs (
                    guild_id INTEGER PRIMARY KEY,
                    officer_role_id INTEGER,
                    notification_channel_id INTEGER,
                    leadership_channel_id INTEGER,
                    dm_users TEXT,
                    membership_roles TEXT,
                    contribution_categories TEXT,
                    loa_notification_role_id INTEGER,
                    loa_notification_channel_id INTEGER,
                    cross_server_notifications BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Members table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    discord_name TEXT NOT NULL,
                    discord_username TEXT,
                    rank TEXT,
                    status TEXT DEFAULT 'Active',
                    is_on_loa BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, user_id)
                )
            ''')
            
            # LOA records table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS loa_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    duration TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_expired BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Contributions table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS contributions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    quantity INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # DM transcripts table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS dm_transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    sender_id INTEGER NOT NULL,
                    recipient_id INTEGER NOT NULL,
                    role_id INTEGER,
                    message TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    recipient_type TEXT NOT NULL,
                    attachments TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Database archives table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS database_archives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    archive_name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    notes TEXT,
                    archived_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by_id INTEGER NOT NULL,
                    FOREIGN KEY (guild_id) REFERENCES guilds (guild_id)
                )
            ''')
            
            # Quantity change log table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS quantity_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    item_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    old_quantity INTEGER NOT NULL,
                    new_quantity INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    notes TEXT,
                    changed_at TEXT NOT NULL,
                    changed_by_id INTEGER NOT NULL,
                    FOREIGN KEY (guild_id) REFERENCES guilds (guild_id)
                )
            ''')
            
            await self._execute_commit()
            logger.info("Database tables initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database tables: {e}")
            raise
    
    async def _migrate_loa_notification_columns(self, conn):
        """Add LOA notification columns to existing server_configs table if they don't exist"""
        try:
            # Check if the new columns exist
            cursor = await conn.execute("PRAGMA table_info(server_configs)")
            columns = [row[1] for row in await cursor.fetchall()]
            
            # Add missing columns
            if 'loa_notification_role_id' not in columns:
                await conn.execute('ALTER TABLE server_configs ADD COLUMN loa_notification_role_id INTEGER')
                logger.info("Added loa_notification_role_id column to server_configs")
            
            if 'loa_notification_channel_id' not in columns:
                await conn.execute('ALTER TABLE server_configs ADD COLUMN loa_notification_channel_id INTEGER')
                logger.info("Added loa_notification_channel_id column to server_configs")
            
            if 'cross_server_notifications' not in columns:
                await conn.execute('ALTER TABLE server_configs ADD COLUMN cross_server_notifications BOOLEAN DEFAULT FALSE')
                logger.info("Added cross_server_notifications column to server_configs")
                
        except Exception as e:
            logger.error(f"Error during LOA notification column migration: {e}")
            # Don't raise here - table creation will handle it
    
    async def _migrate_dm_users_column(self, conn):
        """Migrate dm_user_id to dm_users JSON array"""
        try:
            # Check if the table exists and what columns it has
            cursor = await conn.execute("PRAGMA table_info(server_configs)")
            columns = {row[1]: row[2] for row in await cursor.fetchall()}
            
            # If dm_user_id exists but dm_users doesn't, we need to migrate
            if 'dm_user_id' in columns and 'dm_users' not in columns:
                logger.info("Migrating dm_user_id to dm_users JSON format")
                
                # Add new dm_users column
                await conn.execute('ALTER TABLE server_configs ADD COLUMN dm_users TEXT')
                
                # Migrate existing dm_user_id values to dm_users JSON array
                cursor = await conn.execute('SELECT guild_id, dm_user_id FROM server_configs WHERE dm_user_id IS NOT NULL')
                rows = await cursor.fetchall()
                
                for guild_id, dm_user_id in rows:
                    # Convert single user ID to JSON array
                    dm_users_json = json.dumps([dm_user_id])
                    await conn.execute(
                        'UPDATE server_configs SET dm_users = ? WHERE guild_id = ?',
                        (dm_users_json, guild_id)
                    )
                
                # Drop the old dm_user_id column
                # Note: SQLite doesn't support DROP COLUMN directly, so we'll leave it for compatibility
                logger.info(f"Migrated {len(rows)} dm_user_id entries to dm_users format")
                
            # If neither exists, dm_users will be created by table creation
            elif 'dm_user_id' not in columns and 'dm_users' not in columns:
                # This will be handled by table creation
                pass
                
        except Exception as e:
            logger.error(f"Error during DM users column migration: {e}")
            # Don't raise here - table creation will handle it
    
    async def initialize_guild(self, guild_id: int):
        """Initialize database for a specific guild"""
        try:
            await self.initialize_database()
            
            # Create default server config if it doesn't exist
            conn = await self._get_shared_connection()
            cursor = await conn.execute(
                'SELECT guild_id FROM server_configs WHERE guild_id = ?',
                (guild_id,)
            )
            if not await cursor.fetchone():
                default_roles = [
                    "President", "Vice President", "Sergeant At Arms",
                    "Secretary", "Treasurer", "Road Captain", "Tailgunner",
                    "Enforcer", "Full Patch", "Full Patch/Nomad"
                ]
                default_categories = [
                    "Body Armour & Medical", "Pistols", "Rifles", "SMGs",
                    "Heist Items", "Dirty Cash", "Drug Items", "Mech Shop", "Crafting Items"
                ]
                
                await conn.execute('''
                    INSERT INTO server_configs (guild_id, membership_roles, contribution_categories)
                    VALUES (?, ?, ?)
                ''', (guild_id, json.dumps(default_roles), json.dumps(default_categories)))
                await self._execute_commit()
                logger.info(f"Default configuration created for guild {guild_id}")
        except Exception as e:
            logger.error(f"Failed to initialize guild {guild_id}: {e}")
            raise
    
    # Server Configuration Methods
    async def get_server_config(self, guild_id: int) -> Optional[Dict]:
        """Get server configuration"""
        conn = await self._get_shared_connection()
        # Set row factory to get dictionary-like rows
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            'SELECT * FROM server_configs WHERE guild_id = ?',
            (guild_id,)
        )
        row = await cursor.fetchone()
        if row:
            # Convert Row object to dictionary
            config = dict(row)
            
            # Parse JSON fields
            if config.get('membership_roles'):
                config['membership_roles'] = json.loads(config['membership_roles'])
            if config.get('contribution_categories'):
                config['contribution_categories'] = json.loads(config['contribution_categories'])
            return config
        return None
    
    async def update_server_config(self, guild_id: int, **kwargs):
        """Update server configuration"""
        conn = await self._get_shared_connection()
        # Convert lists to JSON strings
        for key, value in kwargs.items():
            if key in ['membership_roles', 'contribution_categories'] and isinstance(value, list):
                kwargs[key] = json.dumps(value)
        
        # Build dynamic update query
        fields = ', '.join(f"{key} = ?" for key in kwargs.keys())
        values = list(kwargs.values()) + [datetime.now(), guild_id]
        
        await conn.execute(f'''
            UPDATE server_configs 
            SET {fields}, updated_at = ?
            WHERE guild_id = ?
        ''', values)
        await self._execute_commit()
    
    # Member Management Methods
    async def add_or_update_member(self, guild_id: int, user_id: int, discord_name: str, rank: str = None, discord_username: str = None, status: str = 'Active'):
        """Add or update a member"""
        try:
            conn = await self._get_shared_connection()
            await conn.execute('''
                INSERT INTO members (guild_id, user_id, discord_name, discord_username, rank, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) 
                DO UPDATE SET discord_name = ?, discord_username = COALESCE(?, discord_username), rank = COALESCE(?, rank), status = COALESCE(?, status), updated_at = ?
            ''', (guild_id, user_id, discord_name, discord_username, rank, status, datetime.now(), 
                  discord_name, discord_username, rank, status, datetime.now()))
            await self._execute_commit()
        except Exception as e:
            logger.error(f"Failed to add/update member {user_id} in guild {guild_id}: {e}")
            raise
    
    async def get_member(self, guild_id: int, user_id: int) -> Optional[Dict]:
        """Get a specific member"""
        conn = await self._get_shared_connection()
        # Set row factory to get dictionary-like rows
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            'SELECT * FROM members WHERE guild_id = ? AND user_id = ?',
            (guild_id, user_id)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    
    async def get_all_members(self, guild_id: int) -> List[Dict]:
        """Get all members for a guild"""
        conn = await self._get_shared_connection()
        # Set row factory to get dictionary-like rows
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            'SELECT * FROM members WHERE guild_id = ? ORDER BY rank, discord_name',
            (guild_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    
    async def update_member_loa_status(self, guild_id: int, user_id: int, is_on_loa: bool):
        """Update member's LOA status"""
        try:
            conn = await self._get_shared_connection()
            await conn.execute('''
                UPDATE members 
                SET is_on_loa = ?, updated_at = ?
                WHERE guild_id = ? AND user_id = ?
            ''', (is_on_loa, datetime.now(), guild_id, user_id))
            await self._execute_commit()
        except Exception as e:
            logger.error(f"Failed to update LOA status for member {user_id} in guild {guild_id}: {e}")
            raise
    
    # LOA Management Methods
    async def create_loa_record(self, guild_id: int, user_id: int, duration: str, 
                              reason: str, start_time: datetime, end_time: datetime) -> int:
        """Create a new LOA record"""
        conn = await self._get_shared_connection()
        cursor = await conn.execute('''
            INSERT INTO loa_records (guild_id, user_id, duration, reason, start_time, end_time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (guild_id, user_id, duration, reason, start_time, end_time))
        await self._execute_commit()
        return cursor.lastrowid
    
    async def get_active_loa(self, guild_id: int, user_id: int) -> Optional[Dict]:
        """Get active LOA for a user"""
        conn = await self._get_shared_connection()
        # Set row factory to get dictionary-like rows
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute('''
            SELECT * FROM loa_records 
            WHERE guild_id = ? AND user_id = ? AND is_active = TRUE AND is_expired = FALSE
            ORDER BY created_at DESC LIMIT 1
        ''', (guild_id, user_id))
        row = await cursor.fetchone()
        return dict(row) if row else None
    
    async def get_expired_loas(self) -> List[Dict]:
        """Get all LOAs that have expired but not yet been processed"""
        conn = await self._get_shared_connection()
        # Set row factory to get dictionary-like rows
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute('''
            SELECT * FROM loa_records 
            WHERE is_active = TRUE AND is_expired = FALSE 
            AND end_time <= ?
        ''', (datetime.now(),))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    
    async def mark_loa_expired(self, loa_id: int):
        """Mark an LOA as expired"""
        conn = await self._get_shared_connection()
        await conn.execute(
            'UPDATE loa_records SET is_expired = TRUE WHERE id = ?',
            (loa_id,)
        )
        await self._execute_commit()
    
    async def end_loa(self, loa_id: int):
        """End an LOA (mark as inactive)"""
        conn = await self._get_shared_connection()
        # Get the LOA record first
        cursor = await conn.execute(
            'SELECT guild_id, user_id FROM loa_records WHERE id = ?',
            (loa_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            guild_id, user_id = row
            
            # Mark LOA as inactive
            await conn.execute(
                'UPDATE loa_records SET is_active = FALSE WHERE id = ?',
                (loa_id,)
            )
            
            # Update member's LOA status
            await self.update_member_loa_status(guild_id, user_id, False)
            
            await self._execute_commit()
    
    # Contribution Methods
    async def add_contribution(self, guild_id: int, user_id: int, category: str, 
                             item_name: str, quantity: int = 1) -> int:
        """Add a contribution record"""
        conn = await self._get_shared_connection()
        cursor = await conn.execute('''
            INSERT INTO contributions (guild_id, user_id, category, item_name, quantity)
            VALUES (?, ?, ?, ?, ?)
        ''', (guild_id, user_id, category, item_name, quantity))
        await self._execute_commit()
        return cursor.lastrowid
    
    async def get_contributions_by_category(self, guild_id: int, category: str) -> List[Dict]:
        """Get all contributions for a specific category"""
        conn = await self._get_shared_connection()
        # Set row factory to get dictionary-like rows
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute('''
            SELECT c.*, m.discord_name
            FROM contributions c
            JOIN members m ON c.guild_id = m.guild_id AND c.user_id = m.user_id
            WHERE c.guild_id = ? AND c.category = ?
            ORDER BY c.created_at DESC
        ''', (guild_id, category))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    
    async def get_all_contributions(self, guild_id: int) -> List[Dict]:
        """Get all contributions for a guild"""
        conn = await self._get_shared_connection()
        # Set row factory to get dictionary-like rows
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute('''
            SELECT c.*, m.discord_name
            FROM contributions c
            JOIN members m ON c.guild_id = m.guild_id AND c.user_id = m.user_id
            WHERE c.guild_id = ?
            ORDER BY c.category, c.created_at DESC
        ''', (guild_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    
    # Backup and Export Methods
    async def export_guild_data(self, guild_id: int) -> Dict:
        """Export all data for a guild"""
        data = {
            'guild_id': guild_id,
            'export_timestamp': datetime.now().isoformat(),
            'server_config': await self.get_server_config(guild_id),
            'members': await self.get_all_members(guild_id),
            'contributions': await self.get_all_contributions(guild_id)
        }
        
        # Get LOA records
        conn = await self._get_shared_connection()
        # Set row factory to get dictionary-like rows
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            'SELECT * FROM loa_records WHERE guild_id = ?',
            (guild_id,)
        )
        rows = await cursor.fetchall()
        data['loa_records'] = [dict(row) for row in rows]
        
        return data

    # DM Transcript Methods
    async def log_dm_transcript(self, guild_id: int, sender_id: int, recipient_id: int, 
                               message: str, message_type: str, recipient_type: str, 
                               role_id: int = None, attachments: List[Dict] = None) -> int:
        """Log a DM transcript entry
        
        Args:
            guild_id: The Discord server ID
            sender_id: User ID of the message sender
            recipient_id: User ID of the message recipient
            message: The content of the message
            message_type: Type of message (e.g., 'outgoing', 'incoming')
            recipient_type: Type of recipient (e.g., 'user', 'role')
            role_id: Optional role ID if message was sent to a role
            attachments: Optional list of attachment dictionaries with url and filename
            
        Returns:
            The ID of the created transcript entry
        """
        try:
            conn = await self._get_shared_connection()
            attachments_json = json.dumps(attachments) if attachments else None
            
            cursor = await conn.execute('''
                INSERT INTO dm_transcripts (
                    guild_id, sender_id, recipient_id, role_id, 
                    message, message_type, recipient_type, attachments
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (guild_id, sender_id, recipient_id, role_id, 
                  message, message_type, recipient_type, attachments_json))
            
            await self._execute_commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to log DM transcript: {e}")
            raise
    
    async def get_user_transcript(self, guild_id: int, user_id: int, limit: int = 100, 
                                offset: int = 0) -> List[Dict]:
        """Get DM transcript entries for a specific user
        
        Args:
            guild_id: The Discord server ID
            user_id: User ID to get transcript for
            limit: Maximum number of entries to return
            offset: Number of entries to skip for pagination
            
        Returns:
            List of transcript entries
        """
        conn = await self._get_shared_connection()
        conn.row_factory = aiosqlite.Row
        
        cursor = await conn.execute('''
            SELECT * FROM dm_transcripts
            WHERE guild_id = ? AND (sender_id = ? OR recipient_id = ?)
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        ''', (guild_id, user_id, user_id, limit, offset))
        
        rows = await cursor.fetchall()
        result = []
        
        for row in rows:
            entry = dict(row)
            # Parse attachments JSON if present
            if entry.get('attachments'):
                entry['attachments'] = json.loads(entry['attachments'])
            result.append(entry)
            
        return result
    
    async def search_transcripts(self, guild_id: int, query: str, limit: int = 50) -> List[Dict]:
        """Search DM transcripts by content
        
        Args:
            guild_id: The Discord server ID
            query: Text to search for in messages
            limit: Maximum number of results to return
            
        Returns:
            List of matching transcript entries
        """
        conn = await self._get_shared_connection()
        conn.row_factory = aiosqlite.Row
        
        # Format the query for LIKE search with wildcards
        search_term = f"%{query}%"
        
        cursor = await conn.execute('''
            SELECT * FROM dm_transcripts
            WHERE guild_id = ? AND message LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (guild_id, search_term, limit))
        
        rows = await cursor.fetchall()
        result = []
        
        for row in rows:
            entry = dict(row)
            # Parse attachments JSON if present
            if entry.get('attachments'):
                entry['attachments'] = json.loads(entry['attachments'])
            result.append(entry)
            
        return result
    
    async def get_recent_dm_conversations(self, guild_id: int, limit: int = 20) -> List[Dict]:
        """Get recent DM conversations, grouped by user
        
        Args:
            guild_id: The Discord server ID
            limit: Maximum number of unique conversations to return
            
        Returns:
            List of recent DM conversations with latest message info
        """
        conn = await self._get_shared_connection()
        conn.row_factory = aiosqlite.Row
        
        # This query gets the most recent message for each unique sender/recipient pair
        cursor = await conn.execute('''
            WITH RankedMessages AS (
                SELECT 
                    t.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY 
                            CASE 
                                WHEN sender_id < recipient_id THEN sender_id || '-' || recipient_id
                                ELSE recipient_id || '-' || sender_id
                            END
                        ORDER BY created_at DESC
                    ) as row_num
                FROM dm_transcripts t
                WHERE guild_id = ?
            )
            SELECT * FROM RankedMessages
            WHERE row_num = 1
            ORDER BY created_at DESC
            LIMIT ?
        ''', (guild_id, limit))
        
        rows = await cursor.fetchall()
        result = []
        
        for row in rows:
            entry = dict(row)
            # Parse attachments JSON if present
            if entry.get('attachments'):
                entry['attachments'] = json.loads(entry['attachments'])
            result.append(entry)
            
        return result
    
    # DM Users Management Methods
    async def add_dm_user(self, guild_id: int, user_id: int) -> bool:
        """Add a user to the DM users list for a guild
        
        Args:
            guild_id: The Discord server ID
            user_id: The Discord user ID to add
            
        Returns:
            True if user was added, False if already exists
        """
        try:
            # Get current DM users
            dm_users = await self.get_dm_users(guild_id)
            
            # Check if user is already in the list
            if user_id in dm_users:
                return False
            
            # Add the user
            dm_users.append(user_id)
            
            # Update the database
            await self.update_server_config(guild_id, dm_users=json.dumps(dm_users))
            
            logger.info(f"Added DM user {user_id} to guild {guild_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add DM user {user_id} to guild {guild_id}: {e}")
            raise
    
    async def remove_dm_user(self, guild_id: int, user_id: int) -> bool:
        """Remove a user from the DM users list for a guild
        
        Args:
            guild_id: The Discord server ID
            user_id: The Discord user ID to remove
            
        Returns:
            True if user was removed, False if not found
        """
        try:
            # Get current DM users
            dm_users = await self.get_dm_users(guild_id)
            
            # Check if user is in the list
            if user_id not in dm_users:
                return False
            
            # Remove the user
            dm_users.remove(user_id)
            
            # Update the database
            dm_users_json = json.dumps(dm_users) if dm_users else None
            await self.update_server_config(guild_id, dm_users=dm_users_json)
            
            logger.info(f"Removed DM user {user_id} from guild {guild_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove DM user {user_id} from guild {guild_id}: {e}")
            raise
    
    async def get_dm_users(self, guild_id: int) -> List[int]:
        """Get all DM users for a guild
        
        Args:
            guild_id: The Discord server ID
            
        Returns:
            List of user IDs configured to receive DMs
        """
        try:
            config = await self.get_server_config(guild_id)
            if not config:
                return []
            
            # Check for new dm_users field first
            if config.get('dm_users'):
                return json.loads(config['dm_users'])
            
            # Fallback to old dm_user_id field for backwards compatibility
            elif config.get('dm_user_id'):
                return [config['dm_user_id']]
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get DM users for guild {guild_id}: {e}")
            return []
    
    async def clear_dm_users(self, guild_id: int):
        """Clear all DM users for a guild
        
        Args:
            guild_id: The Discord server ID
        """
        try:
            await self.update_server_config(guild_id, dm_users=None)
            logger.info(f"Cleared all DM users for guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Failed to clear DM users for guild {guild_id}: {e}")
            raise
    
    async def set_dm_users(self, guild_id: int, user_ids: List[int]):
        """Set the DM users list for a guild (replaces existing list)
        
        Args:
            guild_id: The Discord server ID
            user_ids: List of user IDs to set as DM users
        """
        try:
            # Remove duplicates while preserving order
            unique_user_ids = list(dict.fromkeys(user_ids))
            
            dm_users_json = json.dumps(unique_user_ids) if unique_user_ids else None
            await self.update_server_config(guild_id, dm_users=dm_users_json)
            
            logger.info(f"Set DM users for guild {guild_id}: {unique_user_ids}")
            
        except Exception as e:
            logger.error(f"Failed to set DM users for guild {guild_id}: {e}")
            raise
    
    # Database Archive Methods
    async def create_database_archive(self, guild_id: int, archive_name: str, 
                                    description: str, notes: str, created_by_id: int) -> int:
        """Create a database archive with current contribution data"""
        try:
            # Get current contribution summary
            contributions = await self.get_all_contributions(guild_id)
            
            # Create summary data
            archive_data = {
                'archived_at': datetime.now().isoformat(),
                'total_contributions': len(contributions),
                'contributions': contributions
            }
            
            conn = await self._get_shared_connection()
            cursor = await conn.execute('''
                INSERT INTO database_archives (guild_id, archive_name, description, notes, 
                                              archived_data, created_at, created_by_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (guild_id, archive_name, description, notes, json.dumps(archive_data), 
                  datetime.now().isoformat(), created_by_id))
            
            archive_id = cursor.lastrowid
            
            # Clear current contributions (archive and reset)
            await conn.execute('DELETE FROM contributions WHERE guild_id = ?', (guild_id,))
            
            await self._execute_commit()
            
            logger.info(f"Created archive '{archive_name}' (ID: {archive_id}) for guild {guild_id}")
            return archive_id
            
        except Exception as e:
            logger.error(f"Failed to create archive for guild {guild_id}: {e}")
            raise
    
    async def get_database_archives(self, guild_id: int) -> List[Dict]:
        """Get all database archives for a guild"""
        conn = await self._get_shared_connection()
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute('''
            SELECT * FROM database_archives 
            WHERE guild_id = ? 
            ORDER BY created_at DESC
        ''', (guild_id,))
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    
    async def get_archive_by_id(self, archive_id: int) -> Optional[Dict]:
        """Get a specific archive by ID"""
        conn = await self._get_shared_connection()
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute('''
            SELECT * FROM database_archives WHERE id = ?
        ''', (archive_id,))
        
        row = await cursor.fetchone()
        if row:
            archive = dict(row)
            # Parse archived data JSON
            archive['archived_data'] = json.loads(archive['archived_data'])
            return archive
        return None
    
    # Quantity Change Methods
    async def log_quantity_change(self, guild_id: int, item_name: str, category: str,
                                old_quantity: int, new_quantity: int, reason: str,
                                notes: str, changed_by_id: int) -> int:
        """Log a quantity change"""
        try:
            conn = await self._get_shared_connection()
            cursor = await conn.execute('''
                INSERT INTO quantity_changes (guild_id, item_name, category, old_quantity,
                                             new_quantity, reason, notes, changed_at, changed_by_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (guild_id, item_name, category, old_quantity, new_quantity, reason,
                  notes, datetime.now().isoformat(), changed_by_id))
            
            change_id = cursor.lastrowid
            await self._execute_commit()
            
            logger.info(f"Logged quantity change for {item_name} in guild {guild_id}: {old_quantity} -> {new_quantity}")
            return change_id
            
        except Exception as e:
            logger.error(f"Failed to log quantity change for {item_name} in guild {guild_id}: {e}")
            raise
    
    async def get_quantity_change_history(self, guild_id: int, item_name: str) -> List[Dict]:
        """Get quantity change history for a specific item"""
        conn = await self._get_shared_connection()
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute('''
            SELECT qc.*, m.discord_name as changed_by_name
            FROM quantity_changes qc
            LEFT JOIN members m ON qc.guild_id = m.guild_id AND qc.changed_by_id = m.user_id
            WHERE qc.guild_id = ? AND qc.item_name = ?
            ORDER BY qc.changed_at DESC
        ''', (guild_id, item_name))
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    
    async def update_item_quantities(self, guild_id: int, item_name: str, category: str, new_total: int):
        """Update item quantities across all contributions to match new total"""
        try:
            conn = await self._get_shared_connection()
            
            # Get all contributions for this item
            cursor = await conn.execute('''
                SELECT id, quantity FROM contributions
                WHERE guild_id = ? AND item_name = ? AND category = ?
                ORDER BY created_at ASC
            ''', (guild_id, item_name, category))
            
            contributions = await cursor.fetchall()
            
            if not contributions:
                return
            
            # Calculate how to distribute the new total across contributions
            if new_total == 0:
                # If new total is 0, delete all contributions for this item
                await conn.execute('''
                    DELETE FROM contributions
                    WHERE guild_id = ? AND item_name = ? AND category = ?
                ''', (guild_id, item_name, category))
            else:
                # Distribute the new total proportionally
                total_current = sum(contrib[1] for contrib in contributions)
                
                if total_current > 0:
                    # Calculate proportional quantities
                    new_quantities = []
                    remaining_total = new_total
                    
                    for i, (contrib_id, current_qty) in enumerate(contributions):
                        if i == len(contributions) - 1:
                            # Last contribution gets the remainder
                            new_qty = max(0, remaining_total)
                        else:
                            # Proportional distribution
                            proportion = current_qty / total_current
                            new_qty = max(0, int(new_total * proportion))
                        
                        new_quantities.append((contrib_id, new_qty))
                        remaining_total -= new_qty
                    
                    # Update each contribution
                    for contrib_id, new_qty in new_quantities:
                        if new_qty == 0:
                            # Remove contributions with 0 quantity
                            await conn.execute(
                                'DELETE FROM contributions WHERE id = ?',
                                (contrib_id,)
                            )
                        else:
                            await conn.execute(
                                'UPDATE contributions SET quantity = ? WHERE id = ?',
                                (new_qty, contrib_id)
                            )
                else:
                    # If all current quantities are 0, just update the first one
                    await conn.execute(
                        'UPDATE contributions SET quantity = ? WHERE id = ?',
                        (new_total, contributions[0][0])
                    )
            
            await self._execute_commit()
            
            logger.info(f"Updated quantities for {item_name} in guild {guild_id} to total {new_total}")
            
        except Exception as e:
            logger.error(f"Failed to update item quantities for {item_name} in guild {guild_id}: {e}")
            raise
