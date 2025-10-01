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
        dir_path = os.path.dirname(db_path)
        if dir_path:  # Only create directory if there is one to create
            os.makedirs(dir_path, exist_ok=True)
        
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
            
            # Migrate dues periods updated_at column
            await self._migrate_dues_periods_updated_at(conn)
            
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
            
            
            # Modern Dues System Tables
            # Dues periods table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS dues_periods (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    period_name TEXT NOT NULL,
                    description TEXT,
                    due_amount REAL NOT NULL DEFAULT 0.0,
                    due_date TIMESTAMP NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by_id INTEGER NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_by_id INTEGER,
                    UNIQUE(guild_id, period_name)
                )
            ''')
            
            # Dues payments table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS dues_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    dues_period_id INTEGER NOT NULL,
                    amount_paid REAL NOT NULL DEFAULT 0.0,
                    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    payment_method TEXT DEFAULT 'Other',
                    payment_status TEXT DEFAULT 'unpaid' CHECK(payment_status IN ('paid', 'unpaid', 'partial', 'exempt', 'overdue')),
                    notes TEXT,
                    updated_by_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, user_id, dues_period_id),
                    FOREIGN KEY (dues_period_id) REFERENCES dues_periods (id) ON DELETE CASCADE
                )
            ''')
            
            # Prospect management tables
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS prospects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    sponsor_id INTEGER NOT NULL,
                    prospect_role_id INTEGER,
                    sponsor_role_id INTEGER,
                    start_date TIMESTAMP NOT NULL,
                    end_date TIMESTAMP,
                    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'patched', 'dropped', 'archived')),
                    strikes INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, user_id)
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS prospect_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    prospect_id INTEGER NOT NULL,
                    assigned_by_id INTEGER NOT NULL,
                    task_name TEXT NOT NULL,
                    task_description TEXT NOT NULL,
                    due_date TIMESTAMP,
                    status TEXT DEFAULT 'assigned' CHECK(status IN ('assigned', 'completed', 'failed', 'overdue')),
                    completed_date TIMESTAMP,
                    completed_by_id INTEGER,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (prospect_id) REFERENCES prospects (id) ON DELETE CASCADE
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS prospect_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    prospect_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    note_text TEXT NOT NULL,
                    is_strike BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (prospect_id) REFERENCES prospects (id) ON DELETE CASCADE
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS prospect_votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    prospect_id INTEGER NOT NULL,
                    started_by_id INTEGER NOT NULL,
                    vote_type TEXT DEFAULT 'patch' CHECK(vote_type IN ('patch', 'drop')),
                    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed', 'cancelled')),
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ended_at TIMESTAMP,
                    ended_by_id INTEGER,
                    result TEXT,
                    FOREIGN KEY (prospect_id) REFERENCES prospects (id) ON DELETE CASCADE
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS prospect_vote_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vote_id INTEGER NOT NULL,
                    voter_id INTEGER NOT NULL,
                    vote_response TEXT NOT NULL CHECK(vote_response IN ('yes', 'no', 'abstain')),
                    voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (vote_id) REFERENCES prospect_votes (id) ON DELETE CASCADE,
                    UNIQUE(vote_id, voter_id)
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
    
    async def _migrate_dues_periods_updated_at(self, conn):
        """Migrate dues_periods table to add updated_at column if missing"""
        try:
            # Check if the updated_at column exists
            cursor = await conn.execute("PRAGMA table_info(dues_periods)")
            columns = [row[1] for row in await cursor.fetchall()]
            
            if 'updated_at' not in columns:
                # Add the updated_at column (SQLite doesn't support non-constant defaults in ALTER TABLE)
                await conn.execute('ALTER TABLE dues_periods ADD COLUMN updated_at TIMESTAMP')
                # Set updated_at to created_at for existing records
                await conn.execute('UPDATE dues_periods SET updated_at = created_at')
                logger.info("Added updated_at column to dues_periods table and populated existing records")
            
            if 'updated_by_id' not in columns:
                # Add the updated_by_id column
                await conn.execute('ALTER TABLE dues_periods ADD COLUMN updated_by_id INTEGER')
                logger.info("Added updated_by_id column to dues_periods table")
            else:
                # Column exists, just update NULL values
                cursor = await conn.execute('''
                    UPDATE dues_periods 
                    SET updated_at = created_at 
                    WHERE updated_at IS NULL
                ''')
                
                rows_updated = cursor.rowcount
                if rows_updated > 0:
                    logger.info(f"Migrated {rows_updated} dues_periods records to populate updated_at column")
                
        except Exception as e:
            logger.error(f"Error during dues_periods updated_at migration: {e}")
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
    
    
    
    
            
    
    # Dues Tracking Methods
    async def create_dues_period(self, guild_id: int, period_name: str, description: str = None, 
                               due_amount: float = 0.0, due_date: datetime = None, 
                               created_by_id: int = None) -> int:
        """Create a new dues period"""
        try:
            conn = await self._get_shared_connection()
            cursor = await conn.execute('''
                INSERT INTO dues_periods (guild_id, period_name, description, due_amount, due_date, created_by_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (guild_id, period_name, description, due_amount, due_date, created_by_id))
            
            period_id = cursor.lastrowid
            await self._execute_commit()
            
            logger.info(f"Created dues period '{period_name}' (ID: {period_id}) for guild {guild_id}")
            return period_id
            
        except Exception as e:
            logger.error(f"Failed to create dues period for guild {guild_id}: {e}")
            raise
    
    async def get_active_dues_periods(self, guild_id: int) -> List[Dict]:
        """Get all active dues periods for a guild"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT dp.*, m.discord_name as created_by_name
                FROM dues_periods dp
                LEFT JOIN members m ON dp.guild_id = m.guild_id AND dp.created_by_id = m.user_id
                WHERE dp.guild_id = ? AND dp.is_active = TRUE
                ORDER BY dp.due_date DESC, dp.created_at DESC
            ''', (guild_id,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get active dues periods for guild {guild_id}: {e}")
            return []
    
    async def get_dues_period_by_id(self, period_id: int) -> Optional[Dict]:
        """Get a specific dues period by ID"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT dp.*, m.discord_name as created_by_name
                FROM dues_periods dp
                LEFT JOIN members m ON dp.guild_id = m.guild_id AND dp.created_by_id = m.user_id
                WHERE dp.id = ?
            ''', (period_id,))
            
            row = await cursor.fetchone()
            return dict(row) if row else None
            
        except Exception as e:
            logger.error(f"Failed to get dues period {period_id}: {e}")
            return None
    
    async def update_dues_payment(self, guild_id: int, user_id: int, dues_period_id: int, 
                                amount_paid: float = 0.0, payment_date: datetime = None, 
                                payment_method: str = None, payment_status: str = 'unpaid', 
                                notes: str = None, is_exempt: bool = False, 
                                updated_by_id: int = None) -> int:
        """Update or create a dues payment record"""
        try:
            conn = await self._get_shared_connection()
            
            # Get existing payment record if it exists
            cursor = await conn.execute('''
                SELECT * FROM dues_payments 
                WHERE guild_id = ? AND user_id = ? AND dues_period_id = ?
            ''', (guild_id, user_id, dues_period_id))
            existing = await cursor.fetchone()
            
            if existing:
                # Update existing record and log history
                old_amount = existing[4]  # amount_paid
                old_status = existing[7]  # payment_status
                old_method = existing[6]  # payment_method
                old_notes = existing[8]   # notes
                
                cursor = await conn.execute('''
                    UPDATE dues_payments 
                    SET amount_paid = ?, payment_date = ?, payment_method = ?, 
                        payment_status = ?, notes = ?, is_exempt = ?, 
                        updated_by_id = ?, updated_at = ?
                    WHERE guild_id = ? AND user_id = ? AND dues_period_id = ?
                ''', (amount_paid, payment_date, payment_method, payment_status, 
                      notes, is_exempt, updated_by_id, datetime.now(),
                      guild_id, user_id, dues_period_id))
                
                payment_id = existing[0]  # id
                
                # Log the change to history
                await conn.execute('''
                    INSERT INTO dues_payment_history 
                    (guild_id, dues_payment_id, action_type, old_amount, new_amount, 
                     old_status, new_status, old_payment_method, new_payment_method,
                     old_notes, new_notes, changed_by_id)
                    VALUES (?, ?, 'updated', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (guild_id, payment_id, old_amount, amount_paid, 
                      old_status, payment_status, old_method, payment_method,
                      old_notes, notes, updated_by_id))
            else:
                # Create new payment record
                cursor = await conn.execute('''
                    INSERT INTO dues_payments 
                    (guild_id, user_id, dues_period_id, amount_paid, payment_date, 
                     payment_method, payment_status, notes, is_exempt, updated_by_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (guild_id, user_id, dues_period_id, amount_paid, payment_date,
                      payment_method, payment_status, notes, is_exempt, updated_by_id))
                
                payment_id = cursor.lastrowid
                
                # Log the creation to history
                await conn.execute('''
                    INSERT INTO dues_payment_history 
                    (guild_id, dues_payment_id, action_type, new_amount, new_status, 
                     new_payment_method, new_notes, changed_by_id)
                    VALUES (?, ?, 'created', ?, ?, ?, ?, ?)
                ''', (guild_id, payment_id, amount_paid, payment_status, 
                      payment_method, notes, updated_by_id))
            
            await self._execute_commit()
            logger.info(f"Updated dues payment for user {user_id} in period {dues_period_id}")
            return payment_id
            
        except Exception as e:
            logger.error(f"Failed to update dues payment: {e}")
            raise
    
    async def get_dues_payments_for_period(self, guild_id: int, dues_period_id: int) -> List[Dict]:
        """Get all dues payments for a specific period with member information"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT dp.*, m.discord_name, m.discord_username, m.rank,
                       updater.discord_name as updated_by_name,
                       per.period_name, per.due_amount
                FROM dues_payments dp
                LEFT JOIN members m ON dp.guild_id = m.guild_id AND dp.user_id = m.user_id
                LEFT JOIN members updater ON dp.guild_id = updater.guild_id AND dp.updated_by_id = updater.user_id
                LEFT JOIN dues_periods per ON dp.dues_period_id = per.id
                WHERE dp.guild_id = ? AND dp.dues_period_id = ?
                ORDER BY m.rank, m.discord_name
            ''', (guild_id, dues_period_id))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get dues payments for period {dues_period_id}: {e}")
            return []
    
    async def get_all_dues_payments_with_members(self, guild_id: int, dues_period_id: int) -> List[Dict]:
        """Get all active members with their dues payment status for a period"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT m.*, 
                       dp.amount_paid, dp.payment_date, dp.payment_method, 
                       dp.payment_status, dp.notes, dp.is_exempt,
                       updater.discord_name as updated_by_name,
                       per.period_name, per.due_amount, per.due_date
                FROM members m
                LEFT JOIN dues_payments dp ON m.guild_id = dp.guild_id AND m.user_id = dp.user_id AND dp.dues_period_id = ?
                LEFT JOIN members updater ON dp.updated_by_id = updater.user_id AND dp.guild_id = updater.guild_id
                LEFT JOIN dues_periods per ON per.id = ? AND per.guild_id = m.guild_id
                WHERE m.guild_id = ? AND m.status = 'Active'
                ORDER BY 
                    CASE m.rank
                        WHEN 'President' THEN 1
                        WHEN 'Vice President' THEN 2
                        WHEN 'Sergeant At Arms' THEN 3
                        WHEN 'Secretary' THEN 4
                        WHEN 'Treasurer' THEN 5
                        WHEN 'Road Captain' THEN 6
                        WHEN 'Tailgunner' THEN 7
                        WHEN 'Enforcer' THEN 8
                        WHEN 'Full Patch' THEN 9
                        WHEN 'Nomad' THEN 10
                        ELSE 999
                    END,
                    m.discord_name
            ''', (dues_period_id, dues_period_id, guild_id))
            
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                member_data = dict(row)
                # Set default values if no payment record exists
                if member_data['amount_paid'] is None:
                    member_data['amount_paid'] = 0.0
                if member_data['payment_status'] is None:
                    member_data['payment_status'] = 'unpaid'
                if member_data['is_exempt'] is None:
                    member_data['is_exempt'] = False
                result.append(member_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get all dues payments with members: {e}")
            return []
    
    async def get_dues_payment_history(self, guild_id: int, dues_payment_id: int) -> List[Dict]:
        """Get payment history for a specific dues payment"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT dph.*, m.discord_name as changed_by_name
                FROM dues_payment_history dph
                LEFT JOIN members m ON dph.guild_id = m.guild_id AND dph.changed_by_id = m.user_id
                WHERE dph.guild_id = ? AND dph.dues_payment_id = ?
                ORDER BY dph.changed_at DESC
            ''', (guild_id, dues_payment_id))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get payment history: {e}")
            return []
    
    async def get_dues_collection_summary(self, guild_id: int, dues_period_id: int) -> Dict:
        """Get collection summary for a dues period"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            
            # Get period info
            cursor = await conn.execute('''
                SELECT * FROM dues_periods WHERE id = ? AND guild_id = ?
            ''', (dues_period_id, guild_id))
            period = await cursor.fetchone()
            
            if not period:
                return {}
            
            period = dict(period)
            
            # Get payment statistics
            cursor = await conn.execute('''
                SELECT 
                    COUNT(DISTINCT m.user_id) as total_members,
                    COUNT(dp.id) as members_with_records,
                    COUNT(CASE WHEN dp.payment_status = 'paid' THEN 1 END) as paid_count,
                    COUNT(CASE WHEN dp.payment_status = 'unpaid' THEN 1 END) as unpaid_count,
                    COUNT(CASE WHEN dp.payment_status = 'partial' THEN 1 END) as partial_count,
                    COUNT(CASE WHEN dp.is_exempt = TRUE THEN 1 END) as exempt_count,
                    COALESCE(SUM(dp.amount_paid), 0) as total_collected,
                    COALESCE(SUM(CASE WHEN dp.is_exempt = FALSE THEN ? ELSE 0 END), 0) as total_expected
                FROM members m
                LEFT JOIN dues_payments dp ON m.guild_id = dp.guild_id AND m.user_id = dp.user_id AND dp.dues_period_id = ?
                WHERE m.guild_id = ? AND m.status = 'Active'
            ''', (period['due_amount'], dues_period_id, guild_id))
            
            stats = dict(await cursor.fetchone())
            
            # Calculate members without records (default to unpaid)
            members_without_records = stats['total_members'] - stats['members_with_records']
            stats['unpaid_count'] += members_without_records
            
            # Calculate collection percentage
            collection_percentage = 0.0
            if stats['total_expected'] > 0:
                collection_percentage = (stats['total_collected'] / stats['total_expected']) * 100
            
            return {
                'period': period,
                'total_members': stats['total_members'],
                'paid_count': stats['paid_count'],
                'unpaid_count': stats['unpaid_count'],
                'partial_count': stats['partial_count'],
                'exempt_count': stats['exempt_count'],
                'total_collected': stats['total_collected'],
                'total_expected': stats['total_expected'],
                'collection_percentage': round(collection_percentage, 1),
                'outstanding_amount': max(0, stats['total_expected'] - stats['total_collected'])
            }
            
        except Exception as e:
            logger.error(f"Failed to get dues collection summary: {e}")
            return {}
    
    async def get_treasury_summary(self, guild_id: int) -> Dict:
        """Get overall treasury summary across all active dues periods"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            
            # Get all active dues periods for the guild
            cursor = await conn.execute('''
                SELECT * FROM dues_periods 
                WHERE guild_id = ? AND is_active = TRUE
                ORDER BY created_at DESC
            ''', (guild_id,))
            
            periods = [dict(row) for row in await cursor.fetchall()]
            
            if not periods:
                return {
                    'total_collected': 0.0,
                    'total_expected': 0.0,
                    'outstanding_amount': 0.0,
                    'active_periods_count': 0,
                    'recent_period_name': None,
                    'collection_percentage': 0.0
                }
            
            # Get aggregated payment statistics across all active periods
            period_ids = [period['id'] for period in periods]
            placeholders = ','.join(['?' for _ in period_ids])
            
            cursor = await conn.execute(f'''
                SELECT 
                    COUNT(DISTINCT m.user_id) as total_members,
                    COALESCE(SUM(dp.amount_paid), 0) as total_collected,
                    COUNT(CASE WHEN dp.payment_status = 'paid' THEN 1 END) as total_paid,
                    COUNT(CASE WHEN dp.payment_status IN ('unpaid', 'partial') THEN 1 END) as total_outstanding_members
                FROM members m
                LEFT JOIN dues_payments dp ON m.guild_id = dp.guild_id AND m.user_id = dp.user_id 
                    AND dp.dues_period_id IN ({placeholders})
                WHERE m.guild_id = ? AND m.status = 'Active'
            ''', (*period_ids, guild_id))
            
            stats = dict(await cursor.fetchone())
            
            # Calculate total expected across all periods
            total_expected = 0.0
            for period in periods:
                # For each period, multiply the due amount by the number of active members
                total_expected += period['due_amount'] * stats['total_members']
            
            # Calculate outstanding amount
            outstanding_amount = max(0, total_expected - stats['total_collected'])
            
            # Calculate collection percentage
            collection_percentage = 0.0
            if total_expected > 0:
                collection_percentage = (stats['total_collected'] / total_expected) * 100
            
            # Get the most recent period name for display
            recent_period_name = periods[0]['period_name'] if periods else None
            
            return {
                'total_collected': round(stats['total_collected'], 2),
                'total_expected': round(total_expected, 2),
                'outstanding_amount': round(outstanding_amount, 2),
                'active_periods_count': len(periods),
                'recent_period_name': recent_period_name,
                'collection_percentage': round(collection_percentage, 1),
                'periods': periods  # Include period details for reference
            }
            
        except Exception as e:
            logger.error(f"Failed to get treasury summary for guild {guild_id}: {e}")
            return {
                'total_collected': 0.0,
                'total_expected': 0.0,
                'outstanding_amount': 0.0,
                'active_periods_count': 0,
                'recent_period_name': None,
                'collection_percentage': 0.0
            }
    
    async def reset_dues_period(self, guild_id: int, dues_period_id: int, reset_by_id: int) -> bool:
        """Reset all payments for a dues period (manual reset)"""
        try:
            conn = await self._get_shared_connection()
            
            # Delete all payments for this period
            cursor = await conn.execute('''
                DELETE FROM dues_payments 
                WHERE guild_id = ? AND dues_period_id = ?
            ''', (guild_id, dues_period_id))
            
            deleted_count = cursor.rowcount
            await self._execute_commit()
            
            logger.info(f"Reset dues period {dues_period_id} - deleted {deleted_count} payment records by user {reset_by_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset dues period {dues_period_id}: {e}")
            return False
    
    # Prospect Management Methods
    async def create_prospect(self, guild_id: int, user_id: int, sponsor_id: int, 
                            prospect_role_id: int = None, sponsor_role_id: int = None) -> int:
        """Create a new prospect record"""
        try:
            conn = await self._get_shared_connection()
            cursor = await conn.execute('''
                INSERT INTO prospects (guild_id, user_id, sponsor_id, prospect_role_id, sponsor_role_id, start_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (guild_id, user_id, sponsor_id, prospect_role_id, sponsor_role_id, datetime.now()))
            
            prospect_id = cursor.lastrowid
            await self._execute_commit()
            
            logger.info(f"Created prospect record for user {user_id} sponsored by {sponsor_id} in guild {guild_id}")
            return prospect_id
            
        except Exception as e:
            logger.error(f"Failed to create prospect: {e}")
            raise
    
    async def get_prospect_by_user(self, guild_id: int, user_id: int) -> Optional[Dict]:
        """Get prospect record by user ID"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT p.*, 
                       sponsor.discord_name as sponsor_name,
                       prospect.discord_name as prospect_name
                FROM prospects p
                LEFT JOIN members sponsor ON p.guild_id = sponsor.guild_id AND p.sponsor_id = sponsor.user_id
                LEFT JOIN members prospect ON p.guild_id = prospect.guild_id AND p.user_id = prospect.user_id
                WHERE p.guild_id = ? AND p.user_id = ?
            ''', (guild_id, user_id))
            
            row = await cursor.fetchone()
            return dict(row) if row else None
            
        except Exception as e:
            logger.error(f"Failed to get prospect by user {user_id}: {e}")
            return None
    
    async def get_active_prospects(self, guild_id: int) -> List[Dict]:
        """Get all active prospects for a guild"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT p.*,
                       sponsor.discord_name as sponsor_name,
                       prospect.discord_name as prospect_name,
                       COUNT(t.id) as total_tasks,
                       COUNT(CASE WHEN t.status = 'completed' THEN 1 END) as completed_tasks,
                       COUNT(CASE WHEN t.status = 'failed' THEN 1 END) as failed_tasks,
                       COUNT(n.id) as total_notes,
                       COUNT(CASE WHEN n.is_strike = TRUE THEN 1 END) as strike_count
                FROM prospects p
                LEFT JOIN members sponsor ON p.guild_id = sponsor.guild_id AND p.sponsor_id = sponsor.user_id
                LEFT JOIN members prospect ON p.guild_id = prospect.guild_id AND p.user_id = prospect.user_id
                LEFT JOIN prospect_tasks t ON p.id = t.prospect_id
                LEFT JOIN prospect_notes n ON p.id = n.prospect_id
                WHERE p.guild_id = ? AND p.status = 'active'
                GROUP BY p.id
                ORDER BY p.start_date DESC
            ''', (guild_id,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get active prospects: {e}")
            return []
    
    async def get_archived_prospects(self, guild_id: int) -> List[Dict]:
        """Get all archived prospects (patched/dropped) for a guild"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT p.*,
                       sponsor.discord_name as sponsor_name,
                       prospect.discord_name as prospect_name,
                       COUNT(t.id) as total_tasks,
                       COUNT(CASE WHEN t.status = 'completed' THEN 1 END) as completed_tasks,
                       COUNT(CASE WHEN t.status = 'failed' THEN 1 END) as failed_tasks,
                       COUNT(n.id) as total_notes,
                       COUNT(CASE WHEN n.is_strike = TRUE THEN 1 END) as strike_count
                FROM prospects p
                LEFT JOIN members sponsor ON p.guild_id = sponsor.guild_id AND p.sponsor_id = sponsor.user_id
                LEFT JOIN members prospect ON p.guild_id = prospect.guild_id AND p.user_id = prospect.user_id
                LEFT JOIN prospect_tasks t ON p.id = t.prospect_id
                LEFT JOIN prospect_notes n ON p.id = n.prospect_id
                WHERE p.guild_id = ? AND p.status IN ('patched', 'dropped', 'archived')
                GROUP BY p.id
                ORDER BY p.end_date DESC, p.updated_at DESC
            ''', (guild_id,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get archived prospects: {e}")
            return []
    
    async def update_prospect_status(self, prospect_id: int, status: str, end_date: datetime = None) -> bool:
        """Update prospect status (active, patched, dropped, archived)"""
        try:
            conn = await self._get_shared_connection()
            
            if end_date is None and status in ['patched', 'dropped']:
                end_date = datetime.now()
            
            await conn.execute('''
                UPDATE prospects 
                SET status = ?, end_date = ?, updated_at = ?
                WHERE id = ?
            ''', (status, end_date, datetime.now(), prospect_id))
            
            await self._execute_commit()
            logger.info(f"Updated prospect {prospect_id} status to {status}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update prospect status: {e}")
            return False
    
    async def update_prospect_strikes(self, prospect_id: int, strikes: int) -> bool:
        """Update prospect strike count"""
        try:
            conn = await self._get_shared_connection()
            await conn.execute('''
                UPDATE prospects 
                SET strikes = ?, updated_at = ?
                WHERE id = ?
            ''', (strikes, datetime.now(), prospect_id))
            
            await self._execute_commit()
            logger.info(f"Updated prospect {prospect_id} strikes to {strikes}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update prospect strikes: {e}")
            return False
    
    # Prospect Task Methods
    async def create_prospect_task(self, guild_id: int, prospect_id: int, assigned_by_id: int,
                                 task_name: str, task_description: str, due_date: datetime = None) -> int:
        """Create a new prospect task"""
        try:
            conn = await self._get_shared_connection()
            cursor = await conn.execute('''
                INSERT INTO prospect_tasks (guild_id, prospect_id, assigned_by_id, task_name, 
                                          task_description, due_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (guild_id, prospect_id, assigned_by_id, task_name, task_description, due_date))
            
            task_id = cursor.lastrowid
            await self._execute_commit()
            
            logger.info(f"Created task '{task_name}' for prospect {prospect_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create prospect task: {e}")
            raise
    
    async def get_prospect_tasks(self, prospect_id: int) -> List[Dict]:
        """Get all tasks for a prospect"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT t.*,
                       assigned_by.discord_name as assigned_by_name,
                       completed_by.discord_name as completed_by_name
                FROM prospect_tasks t
                LEFT JOIN members assigned_by ON t.guild_id = assigned_by.guild_id AND t.assigned_by_id = assigned_by.user_id
                LEFT JOIN members completed_by ON t.guild_id = completed_by.guild_id AND t.completed_by_id = completed_by.user_id
                WHERE t.prospect_id = ?
                ORDER BY t.created_at DESC
            ''', (prospect_id,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get prospect tasks: {e}")
            return []
    
    async def get_overdue_tasks(self, guild_id: int) -> List[Dict]:
        """Get all overdue prospect tasks"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT t.*,
                       p.user_id as prospect_user_id,
                       p.sponsor_id,
                       prospect.discord_name as prospect_name,
                       sponsor.discord_name as sponsor_name,
                       assigned_by.discord_name as assigned_by_name
                FROM prospect_tasks t
                JOIN prospects p ON t.prospect_id = p.id
                LEFT JOIN members prospect ON p.guild_id = prospect.guild_id AND p.user_id = prospect.user_id
                LEFT JOIN members sponsor ON p.guild_id = sponsor.guild_id AND p.sponsor_id = sponsor.user_id
                LEFT JOIN members assigned_by ON t.guild_id = assigned_by.guild_id AND t.assigned_by_id = assigned_by.user_id
                WHERE t.guild_id = ? 
                  AND t.status = 'assigned' 
                  AND t.due_date <= ?
                  AND p.status = 'active'
                ORDER BY t.due_date ASC
            ''', (guild_id, datetime.now()))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get overdue tasks: {e}")
            return []
    
    async def complete_prospect_task(self, task_id: int, completed_by_id: int, notes: str = None) -> bool:
        """Mark a prospect task as completed"""
        try:
            conn = await self._get_shared_connection()
            await conn.execute('''
                UPDATE prospect_tasks 
                SET status = 'completed', completed_date = ?, completed_by_id = ?, 
                    notes = ?, updated_at = ?
                WHERE id = ?
            ''', (datetime.now(), completed_by_id, notes, datetime.now(), task_id))
            
            await self._execute_commit()
            logger.info(f"Completed prospect task {task_id} by user {completed_by_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to complete prospect task: {e}")
            return False
    
    async def fail_prospect_task(self, task_id: int, completed_by_id: int, notes: str = None) -> bool:
        """Mark a prospect task as failed"""
        try:
            conn = await self._get_shared_connection()
            await conn.execute('''
                UPDATE prospect_tasks 
                SET status = 'failed', completed_date = ?, completed_by_id = ?, 
                    notes = ?, updated_at = ?
                WHERE id = ?
            ''', (datetime.now(), completed_by_id, notes, datetime.now(), task_id))
            
            await self._execute_commit()
            logger.info(f"Failed prospect task {task_id} by user {completed_by_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to fail prospect task: {e}")
            return False
    
    # Prospect Notes Methods
    async def add_prospect_note(self, guild_id: int, prospect_id: int, author_id: int,
                              note_text: str, is_strike: bool = False) -> int:
        """Add a note to a prospect's record"""
        try:
            conn = await self._get_shared_connection()
            cursor = await conn.execute('''
                INSERT INTO prospect_notes (guild_id, prospect_id, author_id, note_text, is_strike)
                VALUES (?, ?, ?, ?, ?)
            ''', (guild_id, prospect_id, author_id, note_text, is_strike))
            
            note_id = cursor.lastrowid
            
            # If this is a strike, update the prospect's strike count
            if is_strike:
                await conn.execute('''
                    UPDATE prospects 
                    SET strikes = (SELECT COUNT(*) FROM prospect_notes WHERE prospect_id = ? AND is_strike = TRUE),
                        updated_at = ?
                    WHERE id = ?
                ''', (prospect_id, datetime.now(), prospect_id))
            
            await self._execute_commit()
            logger.info(f"Added {'strike' if is_strike else 'note'} to prospect {prospect_id} by user {author_id}")
            return note_id
            
        except Exception as e:
            logger.error(f"Failed to add prospect note: {e}")
            raise
    
    async def get_prospect_notes(self, prospect_id: int) -> List[Dict]:
        """Get all notes for a prospect"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT n.*, m.discord_name as author_name, m.rank as author_rank
                FROM prospect_notes n
                LEFT JOIN members m ON n.guild_id = m.guild_id AND n.author_id = m.user_id
                WHERE n.prospect_id = ?
                ORDER BY n.created_at DESC
            ''', (prospect_id,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get prospect notes: {e}")
            return []
    
    # Prospect Voting Methods
    async def create_prospect_vote(self, guild_id: int, prospect_id: int, started_by_id: int,
                                 vote_type: str = 'patch') -> int:
        """Create a new prospect vote"""
        try:
            conn = await self._get_shared_connection()
            
            # Check if there's already an active vote for this prospect
            cursor = await conn.execute('''
                SELECT id FROM prospect_votes 
                WHERE prospect_id = ? AND status = 'active'
            ''', (prospect_id,))
            
            if await cursor.fetchone():
                raise ValueError("There is already an active vote for this prospect")
            
            cursor = await conn.execute('''
                INSERT INTO prospect_votes (guild_id, prospect_id, started_by_id, vote_type)
                VALUES (?, ?, ?, ?)
            ''', (guild_id, prospect_id, started_by_id, vote_type))
            
            vote_id = cursor.lastrowid
            await self._execute_commit()
            
            logger.info(f"Created {vote_type} vote for prospect {prospect_id} by user {started_by_id}")
            return vote_id
            
        except Exception as e:
            logger.error(f"Failed to create prospect vote: {e}")
            raise
    
    async def get_active_prospect_vote(self, prospect_id: int) -> Optional[Dict]:
        """Get active vote for a prospect"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT v.*, 
                       starter.discord_name as started_by_name,
                       p.user_id as prospect_user_id,
                       prospect.discord_name as prospect_name
                FROM prospect_votes v
                LEFT JOIN members starter ON v.guild_id = starter.guild_id AND v.started_by_id = starter.user_id
                JOIN prospects p ON v.prospect_id = p.id
                LEFT JOIN members prospect ON p.guild_id = prospect.guild_id AND p.user_id = prospect.user_id
                WHERE v.prospect_id = ? AND v.status = 'active'
            ''', (prospect_id,))
            
            row = await cursor.fetchone()
            return dict(row) if row else None
            
        except Exception as e:
            logger.error(f"Failed to get active prospect vote: {e}")
            return None
    
    async def cast_prospect_vote(self, vote_id: int, voter_id: int, vote_response: str) -> bool:
        """Cast or update a vote response"""
        try:
            conn = await self._get_shared_connection()
            await conn.execute('''
                INSERT INTO prospect_vote_responses (vote_id, voter_id, vote_response)
                VALUES (?, ?, ?)
                ON CONFLICT(vote_id, voter_id) 
                DO UPDATE SET vote_response = ?, updated_at = CURRENT_TIMESTAMP
            ''', (vote_id, voter_id, vote_response, vote_response))
            
            await self._execute_commit()
            logger.info(f"Cast vote: {vote_response} for vote {vote_id} by voter {voter_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cast prospect vote: {e}")
            return False
    
    async def get_vote_responses(self, vote_id: int, include_voter_ids: bool = False) -> Dict:
        """Get vote responses summary (anonymous unless include_voter_ids is True)"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            
            if include_voter_ids:
                # Include voter information (for bot owner)
                cursor = await conn.execute('''
                    SELECT vr.*, m.discord_name as voter_name
                    FROM prospect_vote_responses vr
                    LEFT JOIN members m ON vr.voter_id = m.user_id
                    WHERE vr.vote_id = ?
                    ORDER BY vr.voted_at ASC
                ''', (vote_id,))
                
                responses = [dict(row) for row in await cursor.fetchall()]
            else:
                # Anonymous summary only
                responses = []
            
            # Get vote counts
            cursor = await conn.execute('''
                SELECT vote_response, COUNT(*) as count
                FROM prospect_vote_responses
                WHERE vote_id = ?
                GROUP BY vote_response
            ''', (vote_id,))
            
            counts = {row[0]: row[1] for row in await cursor.fetchall()}
            
            return {
                'yes': counts.get('yes', 0),
                'no': counts.get('no', 0),
                'abstain': counts.get('abstain', 0),
                'total': sum(counts.values()),
                'responses': responses if include_voter_ids else []
            }
            
        except Exception as e:
            logger.error(f"Failed to get vote responses: {e}")
            return {'yes': 0, 'no': 0, 'abstain': 0, 'total': 0, 'responses': []}
    
    async def end_prospect_vote(self, vote_id: int, ended_by_id: int, result: str = None) -> bool:
        """End a prospect vote and record result"""
        try:
            conn = await self._get_shared_connection()
            
            # Calculate result if not provided
            if result is None:
                vote_summary = await self.get_vote_responses(vote_id)
                total_votes = vote_summary['total']
                yes_votes = vote_summary['yes']
                
                # Unanimous requirement
                if total_votes > 0 and yes_votes == total_votes:
                    result = 'passed'
                else:
                    result = 'failed'
            
            await conn.execute('''
                UPDATE prospect_votes 
                SET status = 'completed', ended_at = ?, ended_by_id = ?, result = ?
                WHERE id = ?
            ''', (datetime.now(), ended_by_id, result, vote_id))
            
            await self._execute_commit()
            logger.info(f"Ended prospect vote {vote_id} with result: {result}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to end prospect vote: {e}")
            return False
    
    async def get_prospect_vote_history(self, prospect_id: int) -> List[Dict]:
        """Get all votes (active and completed) for a prospect"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT v.*, 
                       starter.discord_name as started_by_name,
                       ender.discord_name as ended_by_name
                FROM prospect_votes v
                LEFT JOIN members starter ON v.guild_id = starter.guild_id AND v.started_by_id = starter.user_id
                LEFT JOIN members ender ON v.guild_id = ender.guild_id AND v.ended_by_id = ender.user_id
                WHERE v.prospect_id = ?
                ORDER BY v.started_at DESC
            ''', (prospect_id,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get prospect vote history: {e}")
            return []
    
    # Dues Management Methods (V2 - using main method above)
    
    
    async def get_user_dues_payment(self, guild_id: int, user_id: int, dues_period_id: int):
        """Get a user's payment for a specific dues period"""
        try:
            conn = await self._get_shared_connection()
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT id, user_id, dues_period_id, amount_paid, payment_date, payment_method,
                       payment_status, notes, updated_by_id, updated_at
                FROM dues_payments 
                WHERE guild_id = ? AND user_id = ? AND dues_period_id = ?
            ''', (guild_id, user_id, dues_period_id))
            
            row = await cursor.fetchone()
            if row:
                return {
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'dues_period_id': row['dues_period_id'],
                    'amount_paid': row['amount_paid'],
                    'payment_date': row['payment_date'],
                    'payment_method': row['payment_method'],
                    'status': row['payment_status'],
                    'notes': row['notes'],
                    'updated_by_id': row['updated_by_id'],
                    'updated_at': row['updated_at']
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user dues payment: {e}")
            return None
    
    
    
    async def deactivate_dues_period(self, guild_id: int, period_id: int, updated_by_id: int):
        """Deactivate a dues period"""
        try:
            conn = await self._get_shared_connection()
            await conn.execute('''
                UPDATE dues_periods 
                SET is_active = 0, updated_at = ?, updated_by_id = ?
                WHERE guild_id = ? AND id = ?
            ''', (datetime.now().isoformat(), updated_by_id, guild_id, period_id))
            
            await self._execute_commit()
            logger.info(f"Deactivated dues period {period_id} for guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Failed to deactivate dues period: {e}")
            raise
    
    # Additional prospect methods for V2 system
    async def add_prospect(self, guild_id: int, user_id: int, sponsor_id: int, 
                          start_date: datetime = None) -> int:
        """Add a new prospect"""
        try:
            conn = await self._get_shared_connection()
            
            if not start_date:
                start_date = datetime.now()
            
            cursor = await conn.execute('''
                INSERT INTO prospects (guild_id, user_id, sponsor_id, start_date, status)
                VALUES (?, ?, ?, ?, 'active')
            ''', (guild_id, user_id, sponsor_id, start_date.isoformat()))
            
            prospect_id = cursor.lastrowid
            await self._execute_commit()
            
            logger.info(f"Added prospect {user_id} sponsored by {sponsor_id} for guild {guild_id}")
            return prospect_id
            
        except Exception as e:
            logger.error(f"Failed to add prospect: {e}")
            raise
    
    async def add_prospect_task(self, guild_id: int, prospect_id: int, assigned_by_id: int,
                               task_name: str, task_description: str, due_date: datetime = None) -> int:
        """Add a task for a prospect"""
        try:
            conn = await self._get_shared_connection()
            
            cursor = await conn.execute('''
                INSERT INTO prospect_tasks (guild_id, prospect_id, assigned_by_id, task_name, 
                                          task_description, due_date, status)
                VALUES (?, ?, ?, ?, ?, ?, 'assigned')
            ''', (guild_id, prospect_id, assigned_by_id, task_name, task_description, 
                  due_date.isoformat() if due_date else None))
            
            task_id = cursor.lastrowid
            await self._execute_commit()
            
            logger.info(f"Added task '{task_name}' for prospect {prospect_id} in guild {guild_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to add prospect task: {e}")
            raise
