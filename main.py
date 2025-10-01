import discord
from discord.ext import commands, tasks
import asyncio
import logging
import json
import os
import sys
from datetime import datetime

# Ensure current directory is in Python path for imports
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.database import DatabaseManager
from utils.time_parser import TimeParser
from utils.loa_notifications import LOANotificationManager

# Setup logging with more detailed configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('thanatos_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Set up logger for this module
logger = logging.getLogger(__name__)

class ThanatosBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        # Load configuration
        self.config = self._load_config()
        
        # Set force sync option from config
        self._force_sync_on_startup = self.config.get('force_sync_on_startup', False)
        
        # Bot owners with total control (add user IDs here)
        self.bot_owners = {
            181143017619587073,  # User with total bot control
            # Add more owner IDs here if needed
        }
        
        # Task state tracking
        self._loa_task_started = False
        
        # Initialize database
        try:
            self.db = DatabaseManager()
            logger.info("Database manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database manager: {e}")
            raise
        
        # Initialize time parser
        try:
            self.time_parser = TimeParser()
            logger.info("Time parser initialized")
        except Exception as e:
            logger.error(f"Failed to initialize time parser: {e}")
            raise
        
        # Initialize LOA notification manager
        try:
            self.loa_notifications = LOANotificationManager(self)
            logger.info("LOA notification manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize LOA notification manager: {e}")
            raise
        
    
    def _load_config(self):
        """Load configuration from config.json"""
        try:
            if os.path.exists('config.json'):
                with open('config.json', 'r') as f:
                    return json.load(f)
            else:
                logger.warning("config.json not found, using default settings")
                return {}
        except Exception as e:
            logger.error(f"Failed to load config.json: {e}")
            return {}
    
    def is_bot_owner(self, user_id: int) -> bool:
        """Check if a user is a bot owner with total control"""
        return user_id in self.bot_owners
    
    async def has_bot_owner_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if the interaction user has bot owner permissions"""
        return self.is_bot_owner(interaction.user.id)
        
    async def setup_hook(self):
        """Load all cogs when bot starts"""
        # Initialize database first
        try:
            await self.db.initialize_database()
            logger.info("Database initialized in setup hook")
        except Exception as e:
            logger.error(f"Failed to initialize database in setup hook: {e}")
        
        cogs = ['cogs.loa_system', 'cogs.membership', 'cogs.contributions', 'cogs.configuration', 'cogs.direct_messaging', 'cogs.database_management', 'cogs.audit_logs', 'cogs.dues', 'cogs.prospect_core', 'cogs.prospect_dashboard', 'cogs.prospect_notifications', 'cogs.enhanced_menu_system', 'cogs.time_converter']
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Successfully loaded {cog}")
            except Exception as e:
                logger.error(f"Failed to load {cog}: {e}")
                # Don't raise here, continue loading other cogs
        
        # Start background tasks after database is initialized
        if not self._loa_task_started and not self.check_loa_expiration.is_running():
            try:
                self.check_loa_expiration.start()
                self._loa_task_started = True
                logger.info("LOA expiration check task started")
            except RuntimeError as e:
                if "threads can only be started once" in str(e):
                    logger.warning("LOA task already started, skipping...")
                    self._loa_task_started = True
                else:
                    logger.error(f"Failed to start LOA expiration check task: {e}")
            except Exception as e:
                logger.error(f"Failed to start LOA expiration check task: {e}")
        elif self.check_loa_expiration.is_running():
            logger.info("LOA expiration check task already running")
            self._loa_task_started = True
        
        # Sync commands (force sync if configured)
        try:
            # Check if force sync is enabled in config
            force_sync = getattr(self, '_force_sync_on_startup', False)
            
            if force_sync:
                # Force sync globally
                synced_global = await self.tree.sync()
                logger.info(f"Force synced {len(synced_global)} global slash command(s)")
                
                # Force sync for each guild
                for guild in self.guilds:
                    try:
                        synced_guild = await self.tree.sync(guild=guild)
                        logger.info(f"Force synced {len(synced_guild)} commands for guild {guild.name}")
                    except Exception as e:
                        logger.warning(f"Failed to sync commands for guild {guild.name}: {e}")
            else:
                # Normal sync
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} slash command(s)")
                
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
    
    async def on_ready(self):
        logger.info(f'{self.user} has landed! (ID: {self.user.id})')
        logger.info(f'Bot is ready and connected to {len(self.guilds)} guild(s)')
        
        # Initialize database for all guilds
        for guild in self.guilds:
            try:
                await self.db.initialize_guild(guild.id)
                logger.info(f"Database initialized for guild: {guild.name} (ID: {guild.id})")
            except Exception as e:
                logger.error(f"Failed to initialize database for guild {guild.name} (ID: {guild.id}): {e}")
        
    
    @commands.command(name="sync")
    async def sync_commands(self, ctx):
        """Force sync slash commands (owner only)"""
        if ctx.author.id not in self.bot_owners:
            await ctx.send("❌ Only bot owners can use this command.")
            return
        
        try:
            # Global sync
            synced = await self.tree.sync()
            await ctx.send(f"✅ Synced {len(synced)} global commands.")
            logger.info(f"Force synced {len(synced)} commands globally")
            
            # Guild-specific sync for current guild if in a guild
            if ctx.guild:
                guild_synced = await self.tree.sync(guild=ctx.guild)
                await ctx.send(f"✅ Synced {len(guild_synced)} commands for this guild.")
                logger.info(f"Force synced {len(guild_synced)} commands for guild {ctx.guild.name}")
        except Exception as e:
            await ctx.send(f"❌ Error syncing commands: {e}")
            logger.error(f"Error force syncing commands: {e}")
    
    async def on_guild_join(self, guild):
        """Initialize database when bot joins a new guild"""
        try:
            await self.db.initialize_guild(guild.id)
            logger.info(f"Joined new guild and initialized database: {guild.name} (ID: {guild.id})")
        except Exception as e:
            logger.error(f"Failed to initialize database for new guild {guild.name} (ID: {guild.id}): {e}")
    
    async def close(self):
        """Graceful shutdown"""
        logger.info("Bot is shutting down...")
        
        # Stop background tasks
        if hasattr(self, 'check_loa_expiration') and not self.check_loa_expiration.is_being_cancelled():
            self.check_loa_expiration.cancel()
            logger.info("LOA expiration check task cancelled")
        
        # Close database connections
        if hasattr(self, 'db'):
            try:
                await self.db.close()
            except Exception as e:
                logger.error(f"Error closing database: {e}")
        
        await super().close()
        logger.info("Bot shutdown complete")
    
    async def on_error(self, event_method: str, *args, **kwargs):
        """Handle all unhandled errors"""
        logger.error(f"Unhandled error in {event_method}", exc_info=True)
    
    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Handle slash command errors"""
        logger.error(f"Command error in {interaction.command}: {error}", exc_info=True)
        
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message(
                    "❌ An error occurred while processing your command. Please try again later.",
                    ephemeral=True
                )
            except Exception:
                pass
        else:
            try:
                await interaction.followup.send(
                    "❌ An error occurred while processing your command. Please try again later.",
                    ephemeral=True
                )
            except Exception:
                pass
    
    @tasks.loop(seconds=30)  # Check every 30 seconds for precise timing
    async def check_loa_expiration(self):
        """Background task to check for expired LOAs with precise timing"""
        try:
            expired_loas = await self.db.get_expired_loas()
            
            if expired_loas:
                logger.info(f"Found {len(expired_loas)} expired LOA(s) to process")
            
            for loa in expired_loas:
                guild = self.get_guild(loa['guild_id'])
                if not guild:
                    # Guild doesn't exist - mark LOA as expired and continue
                    logger.warning(f"LOA {loa['id']} belongs to non-existent guild {loa['guild_id']}, marking as expired")
                    await self.db.mark_loa_expired(loa['id'])
                    continue
                
                member = guild.get_member(loa['user_id'])
                if not member:
                    # Member not in guild - mark LOA as expired and continue
                    logger.warning(f"LOA {loa['id']} belongs to user {loa['user_id']} who is no longer in guild {loa['guild_id']}, marking as expired")
                    await self.db.mark_loa_expired(loa['id'])
                    continue
                
                # Use notification manager for LOA expiration
                await self.loa_notifications.notify_loa_expired(guild.id, member, loa)
                
                # Mark as expired in database (but don't remove yet)
                await self.db.mark_loa_expired(loa['id'])
                logger.info(f"Processed expired LOA for user {loa['user_id']} in guild {loa['guild_id']}")
                
        except Exception as e:
            logger.error(f"Error checking LOA expiration: {e}", exc_info=True)
    
    @check_loa_expiration.before_loop
    async def before_check_loa_expiration(self):
        await self.wait_until_ready()
        logger.info("LOA expiration check task is ready to start")

def main():
    """Load bot token and run"""
    if not os.path.exists('config.json'):
        # Create default config file
        default_config = {
            "token": "YOUR_BOT_TOKEN_HERE",
            "database_path": "data/thanatos.db"
        }
        with open('config.json', 'w') as f:
            json.dump(default_config, f, indent=4)
        
        logger.info("Config file created! Please add your bot token to config.json")
        print("Config file created! Please add your bot token to config.json")
        return
    
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    if config['token'] == "YOUR_BOT_TOKEN_HERE":
        logger.error("Bot token not configured in config.json")
        print("Please set your bot token in config.json")
        return
    
    try:
        bot = ThanatosBot()
        logger.info("Starting Thanatos Bot...")
        bot.run(config['token'])
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    main()
