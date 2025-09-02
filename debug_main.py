import discord
from discord.ext import commands, tasks
import asyncio
import logging
import json
import os
import sys
import traceback
from datetime import datetime

# Ensure current directory is in Python path for imports
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.database import DatabaseManager
from utils.time_parser import TimeParser
from utils.loa_notifications import LOANotificationManager
from utils.precise_reminder_system import PreciseReminderSystem

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Enhanced logging configuration with DEBUG level and separate log files
DEBUG_FORMAT = '%(asctime)s - [%(levelname)8s] - %(name)s:%(funcName)s:%(lineno)d - %(message)s'
INFO_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Create multiple loggers for different components
def setup_logging():
    # Root logger setup with DEBUG level
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Debug file handler (everything)
    debug_handler = logging.FileHandler('logs/thanatos_debug.log', encoding='utf-8')
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(logging.Formatter(DEBUG_FORMAT))
    root_logger.addHandler(debug_handler)
    
    # Info file handler (info and above)
    info_handler = logging.FileHandler('logs/thanatos_info.log', encoding='utf-8')
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(logging.Formatter(INFO_FORMAT))
    root_logger.addHandler(info_handler)
    
    # Error file handler (errors only)
    error_handler = logging.FileHandler('logs/thanatos_errors.log', encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(DEBUG_FORMAT))
    root_logger.addHandler(error_handler)
    
    # Console handler with color coding for different levels
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColoredFormatter(INFO_FORMAT))
    root_logger.addHandler(console_handler)
    
    # Set specific loggers to DEBUG level
    logging.getLogger('__main__').setLevel(logging.DEBUG)
    logging.getLogger('utils').setLevel(logging.DEBUG)
    logging.getLogger('cogs').setLevel(logging.DEBUG)
    
    # Discord.py logging (keep at INFO to avoid spam)
    logging.getLogger('discord').setLevel(logging.INFO)
    logging.getLogger('discord.http').setLevel(logging.WARNING)
    logging.getLogger('discord.gateway').setLevel(logging.INFO)

class ColoredFormatter(logging.Formatter):
    """Colored console formatter for better readability"""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset_color = self.COLORS['RESET']
        
        # Add color to the level name
        record.levelname = f"{log_color}{record.levelname}{reset_color}"
        
        return super().format(record)

# Setup enhanced logging
setup_logging()
logger = logging.getLogger(__name__)

class EnhancedThanatosBot(commands.Bot):
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
        
        # Bot owners with total control
        self.bot_owners = {
            181143017619587073,  # User with total bot control
        }
        
        # Enhanced monitoring attributes
        self.command_usage = {}
        self.error_count = 0
        self.start_time = datetime.now()
        self.guild_events = {}
        
        # Task state tracking
        self._loa_task_started = False
        self._event_task_started = False
        
        logger.info("🚀 Enhanced Thanatos Bot initializing with DEBUG monitoring...")
        
        # Initialize components with detailed logging
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all bot components with detailed logging"""
        try:
            logger.debug("Initializing database manager...")
            self.db = DatabaseManager()
            logger.info("✅ Database manager initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database manager: {e}")
            logger.debug(f"Database init traceback: {traceback.format_exc()}")
            raise
        
        try:
            logger.debug("Initializing time parser...")
            self.time_parser = TimeParser()
            logger.info("✅ Time parser initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize time parser: {e}")
            logger.debug(f"Time parser init traceback: {traceback.format_exc()}")
            raise
        
        try:
            logger.debug("Initializing LOA notification manager...")
            self.loa_notifications = LOANotificationManager(self)
            logger.info("✅ LOA notification manager initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize LOA notification manager: {e}")
            logger.debug(f"LOA notifications init traceback: {traceback.format_exc()}")
            raise
        
        try:
            logger.debug("Initializing precise reminder system...")
            self.precise_reminders = PreciseReminderSystem(self)
            logger.info("✅ Precise reminder system initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize precise reminder system: {e}")
            logger.debug(f"Precise reminders init traceback: {traceback.format_exc()}")
            raise
    
    def is_bot_owner(self, user_id: int) -> bool:
        """Check if a user is a bot owner with total control"""
        return user_id in self.bot_owners
    
    async def has_bot_owner_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if the interaction user has bot owner permissions"""
        return self.is_bot_owner(interaction.user.id)
    
    async def setup_hook(self):
        """Load all cogs when bot starts with detailed monitoring"""
        logger.info("🔧 Setup hook started - initializing database and loading cogs...")
        
        # Initialize database first
        try:
            logger.debug("Initializing main database in setup hook...")
            await self.db.initialize_database()
            logger.info("✅ Database initialized in setup hook")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database in setup hook: {e}")
            logger.debug(f"Database setup traceback: {traceback.format_exc()}")
        
        # Load all cogs with detailed monitoring
        cogs = [
            'cogs.loa_system', 
            'cogs.membership', 
            'cogs.contributions', 
            'cogs.configuration', 
            'cogs.backup', 
            'cogs.direct_messaging', 
            'cogs.database_management', 
            'cogs.enhanced_menu_system', 
            'cogs.audit_logs', 
            'cogs.events', 
            'cogs.event_notepad',
            'cogs.dues_tracking',
            'cogs.prospect_core',
            'cogs.prospect_management',
            'cogs.prospect_dashboard',
            'cogs.prospect_notifications'
        ]
        
        loaded_count = 0
        failed_count = 0
        
        for cog in cogs:
            try:
                logger.debug(f"Loading cog: {cog}")
                await self.load_extension(cog)
                loaded_count += 1
                logger.info(f"✅ Successfully loaded {cog}")
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ Failed to load {cog}: {e}")
                logger.debug(f"Cog {cog} load traceback: {traceback.format_exc()}")
        
        logger.info(f"📊 Cog loading complete: {loaded_count} loaded, {failed_count} failed")
        
        # Start background tasks with monitoring
        await self._start_background_tasks()
        
        # Sync commands with monitoring
        try:
            logger.debug("Syncing slash commands...")
            synced = await self.tree.sync()
            logger.info(f"✅ Synced {len(synced)} slash command(s)")
            
            # Log all synced commands for debugging
            for command in synced:
                logger.debug(f"Synced command: /{command.name} - {command.description}")
                
        except Exception as e:
            logger.error(f"❌ Failed to sync commands: {e}")
            logger.debug(f"Command sync traceback: {traceback.format_exc()}")
    
    async def _start_background_tasks(self):
        """Start background tasks with enhanced monitoring"""
        logger.info("🔄 Starting background tasks...")
        
        # Start LOA expiration check
        if not self._loa_task_started and not self.check_loa_expiration.is_running():
            try:
                logger.debug("Starting LOA expiration check task...")
                self.check_loa_expiration.start()
                self._loa_task_started = True
                logger.info("✅ LOA expiration check task started")
            except RuntimeError as e:
                if "threads can only be started once" in str(e):
                    logger.warning("⚠️ LOA task already started, skipping...")
                    self._loa_task_started = True
                else:
                    logger.error(f"❌ Failed to start LOA expiration check task: {e}")
                    logger.debug(f"LOA task start traceback: {traceback.format_exc()}")
            except Exception as e:
                logger.error(f"❌ Failed to start LOA expiration check task: {e}")
                logger.debug(f"LOA task start traceback: {traceback.format_exc()}")
        elif self.check_loa_expiration.is_running():
            logger.info("ℹ️ LOA expiration check task already running")
            self._loa_task_started = True
        
        # Start event reminder task
        if not self._event_task_started and not self.check_event_reminders.is_running():
            try:
                logger.debug("Starting event reminder check task...")
                self.check_event_reminders.start()
                self._event_task_started = True
                logger.info("✅ Event reminder check task started")
            except RuntimeError as e:
                if "threads can only be started once" in str(e):
                    logger.warning("⚠️ Event task already started, skipping...")
                    self._event_task_started = True
                else:
                    logger.error(f"❌ Failed to start event reminder check task: {e}")
                    logger.debug(f"Event task start traceback: {traceback.format_exc()}")
            except Exception as e:
                logger.error(f"❌ Failed to start event reminder check task: {e}")
                logger.debug(f"Event task start traceback: {traceback.format_exc()}")
        elif self.check_event_reminders.is_running():
            logger.info("ℹ️ Event reminder check task already running")
            self._event_task_started = True
    
    async def on_ready(self):
        uptime = datetime.now() - self.start_time
        logger.info(f"🌟 {self.user} has landed! (ID: {self.user.id})")
        logger.info(f"🏠 Bot is ready and connected to {len(self.guilds)} guild(s)")
        logger.info(f"⏱️ Startup time: {uptime.total_seconds():.2f} seconds")
        
        # Log detailed guild information
        for guild in self.guilds:
            logger.debug(f"Connected to guild: {guild.name} (ID: {guild.id}, Members: {guild.member_count})")
            
            try:
                logger.debug(f"Initializing database for guild: {guild.name}")
                await self.db.initialize_guild(guild.id)
                logger.info(f"✅ Database initialized for guild: {guild.name} (ID: {guild.id})")
            except Exception as e:
                logger.error(f"❌ Failed to initialize database for guild {guild.name} (ID: {guild.id}): {e}")
                logger.debug(f"Guild {guild.id} DB init traceback: {traceback.format_exc()}")
        
        # Start precise reminder system with monitoring
        try:
            logger.debug("Starting precise reminder system...")
            await self.precise_reminders.start()
            await self.precise_reminders.refresh_reminders_from_database()
            logger.info("⏰ Precise reminder system started with 1-second accuracy")
        except Exception as e:
            logger.error(f"❌ Failed to start precise reminder system: {e}")
            logger.debug(f"Precise reminders start traceback: {traceback.format_exc()}")
        
        logger.info("🎉 Bot initialization complete and ready for commands!")
    
    async def on_command(self, ctx):
        """Monitor all prefix commands"""
        logger.debug(f"Prefix command used: {ctx.command.name} by {ctx.author} in {ctx.guild}")
        
        # Track command usage
        cmd_name = ctx.command.name
        self.command_usage[cmd_name] = self.command_usage.get(cmd_name, 0) + 1
    
    async def on_app_command_completion(self, interaction: discord.Interaction, command):
        """Monitor successful slash command completions"""
        logger.info(f"✅ Slash command completed: /{command.name} by {interaction.user} in {interaction.guild}")
        logger.debug(f"Command details - User ID: {interaction.user.id}, Guild ID: {interaction.guild.id if interaction.guild else 'DM'}")
        
        # Track command usage
        cmd_name = f"/{command.name}"
        self.command_usage[cmd_name] = self.command_usage.get(cmd_name, 0) + 1
    
    async def on_interaction(self, interaction: discord.Interaction):
        """Monitor all interactions (commands, buttons, modals, etc.)"""
        interaction_type = interaction.type.name
        
        if interaction_type == "application_command":
            logger.debug(f"Slash command interaction: /{interaction.command.name} by {interaction.user}")
        elif interaction_type == "component":
            logger.debug(f"Component interaction: {interaction.data.get('custom_id', 'unknown')} by {interaction.user}")
        elif interaction_type == "modal_submit":
            logger.debug(f"Modal submit interaction: {interaction.data.get('custom_id', 'unknown')} by {interaction.user}")
        else:
            logger.debug(f"Other interaction: {interaction_type} by {interaction.user}")
    
    @commands.command(name="sync")
    async def sync_commands(self, ctx):
        """Force sync slash commands (owner only)"""
        logger.info(f"Sync command requested by {ctx.author} (ID: {ctx.author.id})")
        
        if ctx.author.id not in self.bot_owners:
            logger.warning(f"Unauthorized sync attempt by {ctx.author} (ID: {ctx.author.id})")
            await ctx.send("❌ Only bot owners can use this command.")
            return
        
        try:
            # Global sync
            logger.debug("Performing global command sync...")
            synced = await self.tree.sync()
            await ctx.send(f"✅ Synced {len(synced)} global commands.")
            logger.info(f"Force synced {len(synced)} commands globally")
            
            # Guild-specific sync for current guild if in a guild
            if ctx.guild:
                logger.debug(f"Performing guild sync for {ctx.guild.name}...")
                guild_synced = await self.tree.sync(guild=ctx.guild)
                await ctx.send(f"✅ Synced {len(guild_synced)} commands for this guild.")
                logger.info(f"Force synced {len(guild_synced)} commands for guild {ctx.guild.name}")
        except Exception as e:
            await ctx.send(f"❌ Error syncing commands: {e}")
            logger.error(f"Error force syncing commands: {e}")
            logger.debug(f"Sync error traceback: {traceback.format_exc()}")
    
    @commands.command(name="debug_stats")
    async def debug_stats(self, ctx):
        """Show bot debugging statistics (owner only)"""
        if ctx.author.id not in self.bot_owners:
            await ctx.send("❌ Only bot owners can use this command.")
            return
        
        uptime = datetime.now() - self.start_time
        
        embed = discord.Embed(
            title="🔍 Bot Debug Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📊 General Stats",
            value=f"**Uptime:** {str(uptime).split('.')[0]}\n"
                  f"**Guilds:** {len(self.guilds)}\n"
                  f"**Users:** {sum(g.member_count for g in self.guilds)}\n"
                  f"**Commands:** {len(self.tree.get_commands())}\n"
                  f"**Error Count:** {self.error_count}",
            inline=True
        )
        
        # Show most used commands
        if self.command_usage:
            top_commands = sorted(self.command_usage.items(), key=lambda x: x[1], reverse=True)[:5]
            command_text = "\n".join([f"{cmd}: {count}" for cmd, count in top_commands])
        else:
            command_text = "No commands used yet"
        
        embed.add_field(
            name="🏆 Top Commands",
            value=command_text,
            inline=True
        )
        
        # Task status
        task_status = f"**LOA Task:** {'✅' if self._loa_task_started else '❌'}\n"
        task_status += f"**Event Task:** {'✅' if self._event_task_started else '❌'}"
        
        embed.add_field(
            name="🔄 Background Tasks",
            value=task_status,
            inline=True
        )
        
        await ctx.send(embed=embed)
        logger.info(f"Debug stats requested by {ctx.author}")
    
    async def on_guild_join(self, guild):
        """Monitor guild joins"""
        logger.info(f"🏠 Joined new guild: {guild.name} (ID: {guild.id}, Members: {guild.member_count})")
        
        try:
            await self.db.initialize_guild(guild.id)
            logger.info(f"✅ Database initialized for new guild: {guild.name}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database for new guild {guild.name}: {e}")
            logger.debug(f"New guild DB init traceback: {traceback.format_exc()}")
    
    async def on_guild_remove(self, guild):
        """Monitor guild leaves"""
        logger.info(f"👋 Left guild: {guild.name} (ID: {guild.id})")
    
    async def on_member_join(self, member):
        """Monitor member joins"""
        logger.debug(f"👤 Member joined {member.guild.name}: {member} (ID: {member.id})")
    
    async def on_member_remove(self, member):
        """Monitor member leaves"""
        logger.debug(f"👋 Member left {member.guild.name}: {member} (ID: {member.id})")
    
    async def close(self):
        """Enhanced graceful shutdown with monitoring"""
        logger.info("🛑 Bot shutdown initiated...")
        
        # Log final statistics
        uptime = datetime.now() - self.start_time
        logger.info(f"📊 Final uptime: {str(uptime).split('.')[0]}")
        logger.info(f"📊 Total errors encountered: {self.error_count}")
        logger.info(f"📊 Commands processed: {sum(self.command_usage.values())}")
        
        # Stop background tasks
        if hasattr(self, 'check_loa_expiration') and not self.check_loa_expiration.is_being_cancelled():
            logger.debug("Stopping LOA expiration check task...")
            self.check_loa_expiration.cancel()
            logger.info("✅ LOA expiration check task cancelled")
        
        if hasattr(self, 'check_event_reminders') and not self.check_event_reminders.is_being_cancelled():
            logger.debug("Stopping event reminder check task...")
            self.check_event_reminders.cancel()
            logger.info("✅ Event reminder check task cancelled")
        
        # Close database connections
        if hasattr(self, 'db'):
            try:
                logger.debug("Closing database connections...")
                await self.db.close()
                logger.info("✅ Database connections closed")
            except Exception as e:
                logger.error(f"❌ Error closing database: {e}")
                logger.debug(f"DB close traceback: {traceback.format_exc()}")
        
        await super().close()
        logger.info("🎯 Bot shutdown complete")
    
    async def on_error(self, event_method: str, *args, **kwargs):
        """Enhanced error handling with detailed logging"""
        self.error_count += 1
        logger.error(f"🚨 Unhandled error in {event_method} (Error #{self.error_count})")
        logger.error(f"Error details: {sys.exc_info()[1]}")
        logger.debug(f"Full traceback:\n{traceback.format_exc()}")
        
        # Log additional context if available
        if args:
            logger.debug(f"Event args: {args}")
        if kwargs:
            logger.debug(f"Event kwargs: {kwargs}")
    
    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Enhanced slash command error handling"""
        self.error_count += 1
        
        logger.error(f"🚨 Command error in /{interaction.command.name} (Error #{self.error_count})")
        logger.error(f"User: {interaction.user} (ID: {interaction.user.id})")
        logger.error(f"Guild: {interaction.guild.name if interaction.guild else 'DM'}")
        logger.error(f"Error: {error}")
        logger.debug(f"Command error traceback:\n{traceback.format_exc()}")
        
        # Try to respond to the user
        error_message = "❌ An error occurred while processing your command. The issue has been logged for investigation."
        
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message(error_message, ephemeral=True)
            except Exception as e:
                logger.debug(f"Failed to send error response: {e}")
        else:
            try:
                await interaction.followup.send(error_message, ephemeral=True)
            except Exception as e:
                logger.debug(f"Failed to send error followup: {e}")
    
    @tasks.loop(seconds=30)  # Check every 30 seconds for precise timing
    async def check_loa_expiration(self):
        """Enhanced LOA expiration checking with detailed monitoring"""
        try:
            logger.debug("🔍 Checking for expired LOAs...")
            expired_loas = await self.db.get_expired_loas()
            
            if expired_loas:
                logger.info(f"📋 Found {len(expired_loas)} expired LOA(s) to process")
            else:
                logger.debug("No expired LOAs found")
            
            for loa in expired_loas:
                logger.debug(f"Processing expired LOA ID {loa['id']} for user {loa['user_id']} in guild {loa['guild_id']}")
                
                guild = self.get_guild(loa['guild_id'])
                if not guild:
                    logger.warning(f"⚠️ LOA {loa['id']} belongs to non-existent guild {loa['guild_id']}, marking as expired")
                    await self.db.mark_loa_expired(loa['id'])
                    continue
                
                member = guild.get_member(loa['user_id'])
                if not member:
                    logger.warning(f"⚠️ LOA {loa['id']} belongs to user {loa['user_id']} who is no longer in guild {loa['guild_id']}, marking as expired")
                    await self.db.mark_loa_expired(loa['id'])
                    continue
                
                # Use notification manager for LOA expiration
                logger.debug(f"Sending expiration notification for LOA {loa['id']}")
                await self.loa_notifications.notify_loa_expired(guild.id, member, loa)
                
                # Mark as expired in database
                await self.db.mark_loa_expired(loa['id'])
                logger.info(f"✅ Processed expired LOA for user {member} in guild {guild.name}")
                
        except Exception as e:
            self.error_count += 1
            logger.error(f"🚨 Error checking LOA expiration (Error #{self.error_count}): {e}")
            logger.debug(f"LOA check traceback:\n{traceback.format_exc()}")
    
    @tasks.loop(minutes=1)  # Check every minute for event reminders
    async def check_event_reminders(self):
        """Enhanced event reminder checking with detailed monitoring"""
        try:
            logger.debug("🔍 Checking for event reminders...")
            events_needing_reminders = await self.db.get_events_needing_reminders()
            
            if events_needing_reminders:
                logger.info(f"📅 Found {len(events_needing_reminders)} event(s) needing reminders")
            else:
                logger.debug("No events needing reminders")
            
            for event in events_needing_reminders:
                logger.debug(f"Processing event reminder for '{event['event_name']}' (ID: {event['id']})")
                
                guild = self.get_guild(event['guild_id'])
                if not guild:
                    logger.warning(f"⚠️ Event {event['id']} belongs to non-existent guild {event['guild_id']}")
                    continue
                
                # Send reminders to all invited members
                invitations = await self.db.get_event_invitations(event['id'])
                logger.debug(f"Sending reminders to {len(invitations)} invited members for event {event['id']}")
                
                for invitation in invitations:
                    member = guild.get_member(invitation['user_id'])
                    if member:
                        try:
                            await self.send_event_reminder_dm(member, event)
                            logger.debug(f"✅ Sent reminder to {member} for event '{event['event_name']}'")
                        except Exception as e:
                            logger.error(f"❌ Failed to send event reminder to {member}: {e}")
                            logger.debug(f"Reminder send traceback:\n{traceback.format_exc()}")
                    else:
                        logger.debug(f"⚠️ Member {invitation['user_id']} not found in guild for event reminder")
                
                # Mark reminder as sent
                await self.db.mark_reminder_sent(event['id'])
                logger.info(f"✅ Sent reminders for event '{event['event_name']}' (ID: {event['id']})")
                
        except Exception as e:
            self.error_count += 1
            logger.error(f"🚨 Error checking event reminders (Error #{self.error_count}): {e}")
            logger.debug(f"Event reminder check traceback:\n{traceback.format_exc()}")
    
    async def send_event_reminder_dm(self, member, event):
        """Send event reminder DM to a member with monitoring"""
        try:
            logger.debug(f"Sending event reminder DM to {member} for event '{event['event_name']}'")
            
            embed = discord.Embed(
                title="🔔 Event Reminder",
                description=f"**{event['event_name']}** is coming up!",
                color=0xFFD700
            )
            
            if event.get('description'):
                embed.add_field(name="Description", value=event['description'], inline=False)
            
            if event.get('event_date'):
                embed.add_field(name="Date & Time", value=f"<t:{int(event['event_date'].timestamp())}:F>", inline=False)
            
            if event.get('location'):
                embed.add_field(name="Location", value=event['location'], inline=False)
            
            await member.send(embed=embed)
            logger.debug(f"✅ Successfully sent event reminder DM to {member}")
            
        except discord.Forbidden:
            logger.warning(f"⚠️ Cannot send DM to {member.display_name} ({member.id}) - DMs disabled")
        except Exception as e:
            logger.error(f"❌ Error sending event reminder DM to {member.id}: {e}")
            logger.debug(f"DM send traceback:\n{traceback.format_exc()}")
    
    @check_loa_expiration.before_loop
    async def before_check_loa_expiration(self):
        await self.wait_until_ready()
        logger.info("🔄 LOA expiration check task is ready to start")
    
    @check_event_reminders.before_loop
    async def before_check_event_reminders(self):
        await self.wait_until_ready()
        logger.info("🔄 Event reminder check task is ready to start")

def main():
    """Load bot token and run with enhanced debugging"""
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
        bot = EnhancedThanatosBot()
        logger.info("🚀 Starting Enhanced Thanatos Bot with full debugging...")
        print("[DEBUG] DEBUG MODE ACTIVE - Check logs/ directory for detailed logging")
        print("[LOGS] Logs available:")
        print("   - logs/thanatos_debug.log (ALL events)")
        print("   - logs/thanatos_info.log (Info level and above)")
        print("   - logs/thanatos_errors.log (Errors only)")
        print("[READY] Enhanced monitoring and debugging enabled!")
        
        bot.run(config['token'], log_handler=None)  # Use our custom logging
    except Exception as e:
        logger.critical(f"💥 Failed to start bot: {e}")
        logger.debug(f"Bot start failure traceback:\n{traceback.format_exc()}")
        raise

if __name__ == '__main__':
    main()
