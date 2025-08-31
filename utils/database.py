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
            
            # Migrate forum channel columns
            await self._migrate_forum_channel_columns(conn)
            
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
                    weapons_locker_forum_channel_id INTEGER,
                    drug_locker_forum_channel_id INTEGER,
                    misc_locker_forum_channel_id INTEGER,
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
                    created_by_id INTEGER NOT NULL
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
                    changed_by_id INTEGER NOT NULL
                )
            ''')
            
            # Events table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    event_name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    event_date TIMESTAMP NOT NULL,
                    location TEXT,
                    max_attendees INTEGER,
                    created_by_id INTEGER NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    reminder_sent BOOLEAN DEFAULT FALSE,
                    reminder_hours_before INTEGER DEFAULT 24,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Event RSVPs table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS event_rsvps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    response TEXT NOT NULL CHECK(response IN ('yes', 'no', 'maybe')),
                    response_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    invited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_reminded TIMESTAMP,
                    notes TEXT,
                    UNIQUE(event_id, user_id),
                    FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
                )
            ''')
            
            # Event invitations table (tracks who was invited)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS event_invitations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    invited_by_id INTEGER NOT NULL,
                    invitation_method TEXT NOT NULL,
                    role_id INTEGER,
                    invited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    dm_sent BOOLEAN DEFAULT FALSE,
                    UNIQUE(event_id, user_id),
                    FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
                )
            ''')
            
            # Event categories table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS event_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    category_name TEXT NOT NULL,
                    description TEXT,
                    color_hex TEXT DEFAULT '#5865F2',
                    emoji TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, category_name)
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
    
    async def _migrate_forum_channel_columns(self, conn):
        """Add forum channel columns to existing server_configs table if they don't exist"""
        try:
            # Check if the new columns exist
            cursor = await conn.execute("PRAGMA table_info(server_configs)")
            columns = [row[1] for row in await cursor.fetchall()]
            
            # Add missing forum channel columns
            if 'weapons_locker_forum_channel_id' not in columns:
                await conn.execute('ALTER TABLE server_configs ADD COLUMN weapons_locker_forum_channel_id INTEGER')
                logger.info("Added weapons_locker_forum_channel_id column to server_configs")
            
            if 'drug_locker_forum_channel_id' not in columns:
                await conn.execute('ALTER TABLE server_configs ADD COLUMN drug_locker_forum_channel_id INTEGER')
                logger.info("Added drug_locker_forum_channel_id column to server_configs")
            
            if 'misc_locker_forum_channel_id' not in columns:
                await conn.execute('ALTER TABLE server_configs ADD COLUMN misc_locker_forum_channel_id INTEGER')
                logger.info("Added misc_locker_forum_channel_id column to server_configs")
                
        except Exception as e:
            logger.error(f"Error during forum channel column migration: {e}")
            # Don't raise here - table creation will handle it
    
    async def get_active_loas_for_guild(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all active LOAs for a specific guild with member information"""
        try:
            conn = await self._get_shared_connection()
            cursor = await conn.execute('''
                SELECT l.*, m.discord_name, m.discord_username
                FROM loa_records l
                JOIN members m ON l.guild_id = m.guild_id AND l.user_id = m.user_id
                WHERE l.guild_id = ? AND l.is_active = TRUE AND l.is_expired = FALSE
                ORDER BY l.end_time ASC
            ''', (guild_id,))
            
            rows = await cursor.fetchall()
            
            active_loas = []
            for row in rows:
                # Convert row to dictionary
                loa_data = {
                    'id': row[0],
                    'guild_id': row[1],
                    'user_id': row[2],
                    'duration': row[3],
                    'reason': row[4],
                    'start_time': row[5],
                    'end_time': row[6],
                    'is_active': row[7],
                    'is_expired': row[8],
                    'created_at': row[9],
                    'discord_name': row[10],
                    'discord_username': row[11]
                }
                active_loas.append(loa_data)
            
            return active_loas
            
        except Exception as e:
            logger.error(f"Error getting active LOAs for guild {guild_id}: {e}")
            return []
    
    async def get_loa_by_id(self, loa_id: int) -> Optional[Dict[str, Any]]:
        """Get LOA details by ID with member information"""
        try:
            conn = await self._get_shared_connection()
            cursor = await conn.execute('''
                SELECT l.*, m.discord_name, m.discord_username
                FROM loa_records l
                JOIN members m ON l.guild_id = m.guild_id AND l.user_id = m.user_id
                WHERE l.id = ?
            ''', (loa_id,))
            
            row = await cursor.fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'guild_id': row[1],
                    'user_id': row[2],
                    'duration': row[3],
                    'reason': row[4],
                    'start_time': row[5],
                    'end_time': row[6],
                    'is_active': row[7],
                    'is_expired': row[8],
                    'created_at': row[9],
                    'discord_name': row[10],
                    'discord_username': row[11]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting LOA by ID {loa_id}: {e}")
            return None
    
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
        """Get a specific member
        
        Returns a dict with a backward-compatible alias 'on_loa' for 'is_on_loa'.
        """
        conn = await self._get_shared_connection()
        # Set row factory to get dictionary-like rows
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            'SELECT * FROM members WHERE guild_id = ? AND user_id = ?',
            (guild_id, user_id)
        )
        row = await cursor.fetchone()
        if row:
            member = dict(row)
            # Backward-compatible alias for tests/older code
            member['on_loa'] = member.get('is_on_loa', False)
            return member
        return None
    
    async def get_all_members(self, guild_id: int) -> List[Dict]:
        """Get all members for a guild
        
        Adds a backward-compatible alias 'on_loa' for each member dict.
        """
        conn = await self._get_shared_connection()
        # Set row factory to get dictionary-like rows
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            'SELECT * FROM members WHERE guild_id = ? ORDER BY rank, discord_name',
            (guild_id,)
        )
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            m = dict(row)
            m['on_loa'] = m.get('is_on_loa', False)
            result.append(m)
        return result
    
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

    async def update_member_status(self, guild_id: int, user_id: int, on_loa: Optional[bool] = None, status: Optional[str] = None):
        """Update a member's status fields.
        
        Args:
            guild_id: Server ID
            user_id: Member ID
            on_loa: If provided, sets is_on_loa and adjusts status to 'LOA'/'Active' if status not explicitly provided
            status: If provided, sets the textual status column
        """
        try:
            conn = await self._get_shared_connection()
            updates = []
            params = []
            # Handle LOA flag first
            if on_loa is not None:
                updates.append('is_on_loa = ?')
                params.append(on_loa)
            if status is not None:
                updates.append('status = ?')
                params.append(status)
            elif on_loa is not None:
                # If status wasn't specified, infer from on_loa
                inferred = 'LOA' if on_loa else 'Active'
                updates.append('status = ?')
                params.append(inferred)
            if not updates:
                return  # Nothing to do
            updates.append('updated_at = ?')
            params.append(datetime.now())
            params.extend([guild_id, user_id])
            await conn.execute(f'''UPDATE members SET {', '.join(updates)} WHERE guild_id = ? AND user_id = ?''', tuple(params))
            await self._execute_commit()
        except Exception as e:
            logger.error(f"Failed to update member status for member {user_id} in guild {guild_id}: {e}")
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
        """Create a database archive with current contribution data and clear audit logs"""
        try:
            # Get current contribution summary
            contributions = await self.get_all_contributions(guild_id)
            
            # Get audit events for archiving
            audit_events = await self.get_all_audit_events(guild_id, limit=None)
            
            # Create summary data
            archive_data = {
                'archived_at': datetime.now().isoformat(),
                'total_contributions': len(contributions),
                'total_audit_events': len(audit_events),
                'contributions': contributions,
                'audit_events': audit_events[:1000]  # Store up to 1000 most recent audit events
            }
            
            conn = await self._get_shared_connection()
            cursor = await conn.execute('''
                INSERT INTO database_archives (guild_id, archive_name, description, notes, 
                                              archived_data, created_at, created_by_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (guild_id, archive_name, description, notes, json.dumps(archive_data), 
                  datetime.now().isoformat(), created_by_id))
            
            archive_id = cursor.lastrowid
            
            # Clear current contributions and audit logs (archive and reset)
            await conn.execute('DELETE FROM contributions WHERE guild_id = ?', (guild_id,))
            await self.clear_audit_logs(guild_id)
            
            await self._execute_commit()
            
            logger.info(f"Created archive '{archive_name}' (ID: {archive_id}) for guild {guild_id} - cleared {len(contributions)} contributions and {len(audit_events)} audit events")
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
    
    async def get_all_audit_events(self, guild_id: int, item_name: Optional[str] = None, category: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
        """Get a unified list of all audit events (contributions and quantity changes) ordered by time desc"""
        conn = await self._get_shared_connection()
        conn.row_factory = aiosqlite.Row
        
        conditions = ["guild_id = ?"]
        params_base = [guild_id]
        filters_contrib = []
        filters_qc = []
        
        if item_name:
            filters_contrib.append("item_name = ?")
            filters_qc.append("item_name = ?")
            params_base.append(item_name)
        if category:
            filters_contrib.append("category = ?")
            filters_qc.append("category = ?")
            params_base.append(category)
        
        contrib_where = " AND ".join(["guild_id = ?"] + filters_contrib)
        qc_where = " AND ".join(["guild_id = ?"] + filters_qc)
        
        sql = f'''
            SELECT 'contribution' AS event_type,
                   c.category AS category,
                   c.item_name AS item_name,
                   c.quantity AS quantity_delta,
                   NULL AS old_quantity,
                   NULL AS new_quantity,
                   NULL AS reason,
                   NULL AS notes,
                   c.created_at AS occurred_at,
                   c.user_id AS actor_id
            FROM contributions c
            WHERE {contrib_where}
            UNION ALL
            SELECT 'quantity_change' AS event_type,
                   qc.category AS category,
                   qc.item_name AS item_name,
                   (qc.new_quantity - qc.old_quantity) AS quantity_delta,
                   qc.old_quantity AS old_quantity,
                   qc.new_quantity AS new_quantity,
                   qc.reason AS reason,
                   qc.notes AS notes,
                   qc.changed_at AS occurred_at,
                   qc.changed_by_id AS actor_id
            FROM quantity_changes qc
            WHERE {qc_where}
            ORDER BY occurred_at DESC
        '''
        
        params = params_base + params_base  # for both parts of UNION
        if limit and isinstance(limit, int) and limit > 0:
            sql += "\n            LIMIT ?"
            params.append(limit)
        
        cursor = await conn.execute(sql, tuple(params))
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
    
    async def get_current_item_quantity(self, guild_id: int, item_name: str, category: str) -> int:
        """Get the current quantity for an item from contributions table
        
        The contributions table already reflects the current state after all quantity changes,
        since update_item_quantities() modifies contributions to match the new totals.
        The quantity_changes table is purely an audit log and should not be added to contributions.
        """
        try:
            conn = await self._get_shared_connection()
            
            # Get sum of all contributions for this item (already reflects current state)
            cursor = await conn.execute('''
                SELECT COALESCE(SUM(quantity), 0) as current_quantity
                FROM contributions
                WHERE guild_id = ? AND item_name = ? AND category = ?
            ''', (guild_id, item_name, category))
            
            row = await cursor.fetchone()
            current_quantity = row[0] if row else 0
            
            logger.debug(f"Current quantity for {item_name} in guild {guild_id}: {current_quantity} "
                        f"(from contributions table)")
            
            return max(0, current_quantity)  # Ensure non-negative
            
        except Exception as e:
            logger.error(f"Failed to get current quantity for {item_name} in guild {guild_id}: {e}")
            raise
    
    async def get_all_current_item_quantities(self, guild_id: int) -> Dict[str, Dict]:
        """Get current quantities for all items from contributions table
        
        The contributions table already reflects current state after quantity changes.
        Returns a dictionary with keys as 'item_name|category' and values as item info with current_quantity
        """
        try:
            conn = await self._get_shared_connection()
            
            # Get all items from contributions table (already reflects current state)
            cursor = await conn.execute('''
                SELECT item_name, category, SUM(quantity) as current_quantity
                FROM contributions
                WHERE guild_id = ?
                GROUP BY item_name, category
                HAVING SUM(quantity) > 0
                ORDER BY category, item_name
            ''', (guild_id,))
            
            items = await cursor.fetchall()
            result = {}
            
            for item_name, category, current_qty in items:
                key = f"{item_name}|{category}"
                result[key] = {
                    'item_name': item_name,
                    'category': category,
                    'total_quantity': current_qty,  # Use consistent naming
                    'current_quantity': current_qty
                }
            
            logger.info(f"Retrieved current quantities for {len(result)} items in guild {guild_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get all current item quantities for guild {guild_id}: {e}")
            raise
    
    async def clear_audit_logs(self, guild_id: int):
        """Clear all audit logs (quantity changes) for a guild"""
        try:
            conn = await self._get_shared_connection()
            cursor = await conn.execute('DELETE FROM quantity_changes WHERE guild_id = ?', (guild_id,))
            rows_deleted = cursor.rowcount
            await self._execute_commit()
            
            logger.info(f"Cleared {rows_deleted} audit log entries for guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Failed to clear audit logs for guild {guild_id}: {e}")
            raise
    
    async def remove_audit_entry(self, guild_id: int, event_type: str, entry_id: int, removed_by_id: int) -> bool:
        """Remove a specific audit log entry
        
        Args:
            guild_id: The Discord server ID
            event_type: Either 'contribution' or 'quantity_change'
            entry_id: The ID of the entry to remove
            removed_by_id: User ID of the admin removing the entry
            
        Returns:
            bool: True if entry was successfully removed, False if not found
        """
        try:
            conn = await self._get_shared_connection()
            
            if event_type == 'contribution':
                # Remove from contributions table
                cursor = await conn.execute(
                    'DELETE FROM contributions WHERE guild_id = ? AND id = ?',
                    (guild_id, entry_id)
                )
            elif event_type == 'quantity_change':
                # Remove from quantity_changes table
                cursor = await conn.execute(
                    'DELETE FROM quantity_changes WHERE guild_id = ? AND id = ?',
                    (guild_id, entry_id)
                )
            else:
                logger.error(f"Invalid event_type: {event_type}")
                return False
            
            rows_deleted = cursor.rowcount
            await self._execute_commit()
            
            if rows_deleted > 0:
                logger.info(f"Admin {removed_by_id} removed {event_type} entry {entry_id} from guild {guild_id}")
                return True
            else:
                logger.warning(f"No {event_type} entry found with ID {entry_id} in guild {guild_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to remove {event_type} entry {entry_id} from guild {guild_id}: {e}")
            raise
    
    async def get_audit_entry_details(self, guild_id: int, event_type: str, entry_id: int) -> Optional[Dict]:
        """Get details of a specific audit entry for confirmation before removal
        
        Args:
            guild_id: The Discord server ID
            event_type: Either 'contribution' or 'quantity_change'
            entry_id: The ID of the entry
            
        Returns:
            Dict with entry details or None if not found
        """
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            
            if event_type == 'contribution':
                cursor = await conn.execute('''
                    SELECT c.*, m.discord_name as contributor_name
                    FROM contributions c
                    LEFT JOIN members m ON c.guild_id = m.guild_id AND c.user_id = m.user_id
                    WHERE c.guild_id = ? AND c.id = ?
                ''', (guild_id, entry_id))
            elif event_type == 'quantity_change':
                cursor = await conn.execute('''
                    SELECT qc.*, m.discord_name as changed_by_name
                    FROM quantity_changes qc
                    LEFT JOIN members m ON qc.guild_id = m.guild_id AND qc.changed_by_id = m.user_id
                    WHERE qc.guild_id = ? AND qc.id = ?
                ''', (guild_id, entry_id))
            else:
                return None
            
            row = await cursor.fetchone()
            return dict(row) if row else None
                
        except Exception as e:
            logger.error(f"Failed to get {event_type} entry {entry_id} details from guild {guild_id}: {e}")
            return None
    
    async def bulk_remove_audit_entries(self, guild_id: int, entries: List[Dict], removed_by_id: int) -> Dict:
        """Remove multiple audit entries in a single transaction
        
        Args:
            guild_id: The Discord server ID
            entries: List of dicts with 'event_type' and 'entry_id' keys
            removed_by_id: User ID of the admin removing the entries
            
        Returns:
            Dict with success/failure counts
        """
        try:
            conn = await self._get_shared_connection()
            
            removed_contributions = 0
            removed_quantity_changes = 0
            failed_removals = []
            
            for entry in entries:
                event_type = entry.get('event_type')
                entry_id = entry.get('entry_id')
                
                if not event_type or not entry_id:
                    failed_removals.append(f"Invalid entry: {entry}")
                    continue
                
                try:
                    if event_type == 'contribution':
                        cursor = await conn.execute(
                            'DELETE FROM contributions WHERE guild_id = ? AND id = ?',
                            (guild_id, entry_id)
                        )
                        if cursor.rowcount > 0:
                            removed_contributions += 1
                        else:
                            failed_removals.append(f"Contribution {entry_id} not found")
                    elif event_type == 'quantity_change':
                        cursor = await conn.execute(
                            'DELETE FROM quantity_changes WHERE guild_id = ? AND id = ?',
                            (guild_id, entry_id)
                        )
                        if cursor.rowcount > 0:
                            removed_quantity_changes += 1
                        else:
                            failed_removals.append(f"Quantity change {entry_id} not found")
                    else:
                        failed_removals.append(f"Invalid event_type: {event_type}")
                        
                except Exception as e:
                    failed_removals.append(f"Error removing {event_type} {entry_id}: {str(e)}")
            
            await self._execute_commit()
            
            total_removed = removed_contributions + removed_quantity_changes
            logger.info(f"Admin {removed_by_id} bulk removed {total_removed} audit entries from guild {guild_id} "
                       f"({removed_contributions} contributions, {removed_quantity_changes} quantity changes)")
            
            return {
                'total_removed': total_removed,
                'contributions_removed': removed_contributions,
                'quantity_changes_removed': removed_quantity_changes,
                'failed_removals': failed_removals,
                'success': total_removed > 0
            }
                
        except Exception as e:
            logger.error(f"Failed to bulk remove audit entries from guild {guild_id}: {e}")
            raise
    
    async def get_active_loas_for_guild(self, guild_id: int) -> List[Dict]:
        """Get all active LOAs for a guild with member information"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            
            cursor = await conn.execute('''
                SELECT l.*, m.discord_name, m.discord_username
                FROM loa_records l
                LEFT JOIN members m ON l.guild_id = m.guild_id AND l.user_id = m.user_id
                WHERE l.guild_id = ? AND l.is_active = TRUE AND l.is_expired = FALSE
                ORDER BY l.end_time ASC
            ''', (guild_id,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get active LOAs for guild {guild_id}: {e}")
            return []
    
    async def get_loa_by_id(self, loa_id: int) -> Optional[Dict]:
        """Get a specific LOA by ID with member information"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            
            cursor = await conn.execute('''
                SELECT l.*, m.discord_name, m.discord_username
                FROM loa_records l
                LEFT JOIN members m ON l.guild_id = m.guild_id AND l.user_id = m.user_id
                WHERE l.id = ?
            ''', (loa_id,))
            
            row = await cursor.fetchone()
            return dict(row) if row else None
                
        except Exception as e:
            logger.error(f"Failed to get LOA {loa_id}: {e}")
            return None
    
    # Event Management Methods
    async def create_event(self, guild_id: int, event_name: str, description: str, 
                          category: str, event_date: datetime, location: str = None, 
                          max_attendees: int = None, created_by_id: int = None,
                          reminder_hours_before: int = 24) -> int:
        """Create a new event"""
        try:
            conn = await self._get_shared_connection()
            cursor = await conn.execute('''
                INSERT INTO events (guild_id, event_name, description, category, event_date,
                                   location, max_attendees, created_by_id, reminder_hours_before)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (guild_id, event_name, description, category, event_date, 
                  location, max_attendees, created_by_id, reminder_hours_before))
            
            event_id = cursor.lastrowid
            await self._execute_commit()
            
            logger.info(f"Created event '{event_name}' (ID: {event_id}) for guild {guild_id}")
            return event_id
            
        except Exception as e:
            logger.error(f"Failed to create event for guild {guild_id}: {e}")
            raise
    
    async def get_event_by_id(self, event_id: int) -> Optional[Dict]:
        """Get event details by ID"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT e.*, m.discord_name as created_by_name
                FROM events e
                LEFT JOIN members m ON e.guild_id = m.guild_id AND e.created_by_id = m.user_id
                WHERE e.id = ?
            ''', (event_id,))
            
            row = await cursor.fetchone()
            return dict(row) if row else None
            
        except Exception as e:
            logger.error(f"Failed to get event {event_id}: {e}")
            return None
    
    async def get_active_events(self, guild_id: int) -> List[Dict]:
        """Get all active events for a guild"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT e.*, m.discord_name as created_by_name,
                       COUNT(r.id) as total_invites,
                       SUM(CASE WHEN r.response = 'yes' THEN 1 ELSE 0 END) as yes_count,
                       SUM(CASE WHEN r.response = 'no' THEN 1 ELSE 0 END) as no_count,
                       SUM(CASE WHEN r.response = 'maybe' THEN 1 ELSE 0 END) as maybe_count
                FROM events e
                LEFT JOIN members m ON e.guild_id = m.guild_id AND e.created_by_id = m.user_id
                LEFT JOIN event_rsvps r ON e.id = r.event_id
                WHERE e.guild_id = ? AND e.is_active = TRUE
                GROUP BY e.id
                ORDER BY e.event_date ASC
            ''', (guild_id,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get active events for guild {guild_id}: {e}")
            return []
    
    async def get_events_needing_reminders(self) -> List[Dict]:
        """Get events that need reminder notifications sent"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT * FROM events
                WHERE is_active = TRUE 
                  AND reminder_sent = FALSE
                  AND datetime(event_date, '-' || reminder_hours_before || ' hours') <= datetime('now')
                  AND event_date > datetime('now')
                ORDER BY event_date ASC
            ''')
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get events needing reminders: {e}")
            return []
    
    async def mark_reminder_sent(self, event_id: int):
        """Mark that reminder has been sent for an event"""
        try:
            conn = await self._get_shared_connection()
            await conn.execute(
                'UPDATE events SET reminder_sent = TRUE WHERE id = ?',
                (event_id,)
            )
            await self._execute_commit()
            
        except Exception as e:
            logger.error(f"Failed to mark reminder sent for event {event_id}: {e}")
            raise
    
    async def invite_user_to_event(self, event_id: int, guild_id: int, user_id: int, 
                                  invited_by_id: int, invitation_method: str, 
                                  role_id: int = None) -> bool:
        """Add a user invitation to an event and automatically RSVP them as 'yes'"""
        try:
            conn = await self._get_shared_connection()
            
            # Add the invitation
            await conn.execute('''
                INSERT INTO event_invitations (event_id, guild_id, user_id, invited_by_id, 
                                              invitation_method, role_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (event_id, guild_id, user_id, invited_by_id, invitation_method, role_id))
            
            # Automatically RSVP the user as 'yes'
            await conn.execute('''
                INSERT INTO event_rsvps (event_id, guild_id, user_id, response, notes)
                VALUES (?, ?, ?, 'yes', 'Automatically RSVP''d upon invitation')
                ON CONFLICT(event_id, user_id) 
                DO UPDATE SET response = 'yes', response_time = CURRENT_TIMESTAMP, 
                              notes = 'Automatically RSVP''d upon invitation'
            ''', (event_id, guild_id, user_id))
            
            await self._execute_commit()
            logger.info(f"Invited user {user_id} to event {event_id} and automatically RSVP'd as 'yes'")
            return True
            
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                return False  # User already invited
            logger.error(f"Failed to invite user {user_id} to event {event_id}: {e}")
            raise
    
    async def record_rsvp(self, event_id: int, guild_id: int, user_id: int, 
                         response: str, notes: str = None) -> bool:
        """Record or update an RSVP response"""
        try:
            conn = await self._get_shared_connection()
            await conn.execute('''
                INSERT INTO event_rsvps (event_id, guild_id, user_id, response, notes)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(event_id, user_id) 
                DO UPDATE SET response = ?, response_time = CURRENT_TIMESTAMP, notes = ?
            ''', (event_id, guild_id, user_id, response, notes, response, notes))
            
            await self._execute_commit()
            logger.info(f"Recorded RSVP for user {user_id} to event {event_id}: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record RSVP for user {user_id} to event {event_id}: {e}")
            raise
    
    async def get_event_rsvps(self, event_id: int) -> Dict[str, List[Dict]]:
        """Get all RSVPs for an event, grouped by response type"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT r.*, m.discord_name, m.rank
                FROM event_rsvps r
                LEFT JOIN members m ON r.guild_id = m.guild_id AND r.user_id = m.user_id
                WHERE r.event_id = ?
                ORDER BY r.response_time ASC
            ''', (event_id,))
            
            rows = await cursor.fetchall()
            rsvps = {'yes': [], 'no': [], 'maybe': []}
            
            for row in rows:
                rsvp_data = dict(row)
                response = rsvp_data['response']
                if response in rsvps:
                    rsvps[response].append(rsvp_data)
            
            return rsvps
            
        except Exception as e:
            logger.error(f"Failed to get RSVPs for event {event_id}: {e}")
            return {'yes': [], 'no': [], 'maybe': []}
    
    async def get_event_invitations(self, event_id: int) -> List[Dict]:
        """Get all invitations sent for an event"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT i.*, m.discord_name, 
                       r.response, r.response_time
                FROM event_invitations i
                LEFT JOIN members m ON i.guild_id = m.guild_id AND i.user_id = m.user_id
                LEFT JOIN event_rsvps r ON i.event_id = r.event_id AND i.user_id = r.user_id
                WHERE i.event_id = ?
                ORDER BY i.invited_at ASC
            ''', (event_id,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get invitations for event {event_id}: {e}")
            return []
    
    async def get_user_rsvp(self, event_id: int, user_id: int) -> Optional[str]:
        """Get a user's RSVP response for an event"""
        try:
            conn = await self._get_shared_connection()
            cursor = await conn.execute(
                'SELECT response FROM event_rsvps WHERE event_id = ? AND user_id = ?',
                (event_id, user_id)
            )
            
            row = await cursor.fetchone()
            return row[0] if row else None
            
        except Exception as e:
            logger.error(f"Failed to get user RSVP for event {event_id}, user {user_id}: {e}")
            return None
    
    async def create_event_category(self, guild_id: int, category_name: str, 
                                   description: str = None, color_hex: str = '#5865F2', 
                                   emoji: str = None) -> int:
        """Create a new event category"""
        try:
            conn = await self._get_shared_connection()
            cursor = await conn.execute('''
                INSERT INTO event_categories (guild_id, category_name, description, color_hex, emoji)
                VALUES (?, ?, ?, ?, ?)
            ''', (guild_id, category_name, description, color_hex, emoji))
            
            category_id = cursor.lastrowid
            await self._execute_commit()
            
            logger.info(f"Created event category '{category_name}' for guild {guild_id}")
            return category_id
            
        except Exception as e:
            logger.error(f"Failed to create event category for guild {guild_id}: {e}")
            raise
    
    async def get_event_categories(self, guild_id: int) -> List[Dict]:
        """Get all active event categories for a guild"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT * FROM event_categories 
                WHERE guild_id = ? AND is_active = TRUE
                ORDER BY category_name ASC
            ''', (guild_id,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get event categories for guild {guild_id}: {e}")
            return []
    
    async def get_event_analytics(self, guild_id: int, days: int = 30) -> Dict:
        """Get event analytics for a specified period"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            
            # Get events in the specified period
            cursor = await conn.execute('''
                SELECT e.*, 
                       COUNT(DISTINCT i.user_id) as total_invited,
                       COUNT(DISTINCT r.user_id) as total_responses,
                       SUM(CASE WHEN r.response = 'yes' THEN 1 ELSE 0 END) as yes_responses,
                       SUM(CASE WHEN r.response = 'no' THEN 1 ELSE 0 END) as no_responses,
                       SUM(CASE WHEN r.response = 'maybe' THEN 1 ELSE 0 END) as maybe_responses
                FROM events e
                LEFT JOIN event_invitations i ON e.id = i.event_id
                LEFT JOIN event_rsvps r ON e.id = r.event_id
                WHERE e.guild_id = ? 
                  AND e.created_at >= datetime('now', '-{} days')
                GROUP BY e.id
                ORDER BY e.event_date DESC
            '''.format(days), (guild_id,))
            
            events = [dict(row) for row in await cursor.fetchall()]
            
            # Calculate summary statistics
            total_events = len(events)
            total_invitations = sum(e['total_invited'] or 0 for e in events)
            total_responses = sum(e['total_responses'] or 0 for e in events)
            total_yes = sum(e['yes_responses'] or 0 for e in events)
            total_no = sum(e['no_responses'] or 0 for e in events)
            total_maybe = sum(e['maybe_responses'] or 0 for e in events)
            
            # Calculate response rate
            response_rate = (total_responses / total_invitations * 100) if total_invitations > 0 else 0
            attendance_rate = (total_yes / total_responses * 100) if total_responses > 0 else 0
            
            # Category breakdown
            category_stats = {}
            for event in events:
                category = event['category']
                if category not in category_stats:
                    category_stats[category] = {'count': 0, 'yes_responses': 0, 'total_responses': 0}
                category_stats[category]['count'] += 1
                category_stats[category]['yes_responses'] += event['yes_responses'] or 0
                category_stats[category]['total_responses'] += event['total_responses'] or 0
            
            return {
                'period_days': days,
                'total_events': total_events,
                'total_invitations': total_invitations,
                'total_responses': total_responses,
                'response_breakdown': {
                    'yes': total_yes,
                    'no': total_no,
                    'maybe': total_maybe
                },
                'response_rate': round(response_rate, 1),
                'attendance_rate': round(attendance_rate, 1),
                'category_stats': category_stats,
                'events': events
            }
            
        except Exception as e:
            logger.error(f"Failed to get event analytics for guild {guild_id}: {e}")
            raise
    
    async def mark_dm_sent(self, event_id: int, user_id: int):
        """Mark that a DM invitation has been sent for an event"""
        try:
            conn = await self._get_shared_connection()
            await conn.execute('''
                UPDATE event_invitations 
                SET dm_sent = TRUE 
                WHERE event_id = ? AND user_id = ?
            ''', (event_id, user_id))
            await self._execute_commit()
            
        except Exception as e:
            logger.error(f"Failed to mark DM sent for event {event_id}, user {user_id}: {e}")
            raise
    
    async def get_events_by_date_range(self, guild_id: int, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get events within a specific date range"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT e.*, m.discord_name as created_by_name,
                       COUNT(r.id) as total_rsvps,
                       SUM(CASE WHEN r.response = 'yes' THEN 1 ELSE 0 END) as yes_count
                FROM events e
                LEFT JOIN members m ON e.guild_id = m.guild_id AND e.created_by_id = m.user_id
                LEFT JOIN event_rsvps r ON e.id = r.event_id
                WHERE e.guild_id = ? 
                  AND e.event_date >= ? 
                  AND e.event_date <= ?
                  AND e.is_active = TRUE
                GROUP BY e.id
                ORDER BY e.event_date ASC
            ''', (guild_id, start_date, end_date))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get events by date range for guild {guild_id}: {e}")
            return []
