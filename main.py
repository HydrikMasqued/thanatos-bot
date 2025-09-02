import discord
from discord.ext import commands, tasks
import asyncio
import logging
import json
import os
from datetime import datetime
from utils.database import DatabaseManager
from utils.time_parser import TimeParser
from utils.loa_notifications import LOANotificationManager
from utils.precise_reminder_system import PreciseReminderSystem

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
        
        # Bot owners with total control (add user IDs here)
        self.bot_owners = {
            181143017619587073,  # User with total bot control
            # Add more owner IDs here if needed
        }
        
        # Task state tracking
        self._loa_task_started = False
        self._event_task_started = False
        
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
        
        # Initialize precise reminder system
        try:
            self.precise_reminders = PreciseReminderSystem(self)
            logger.info("Precise reminder system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize precise reminder system: {e}")
            raise
    
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
        
        cogs = ['cogs.loa_system', 'cogs.membership', 'cogs.contributions', 'cogs.configuration', 'cogs.direct_messaging', 'cogs.database_management', 'cogs.audit_logs', 'cogs.events', 'cogs.event_notepad', 'cogs.dues_tracking', 'cogs.prospect_core', 'cogs.prospect_dashboard', 'cogs.prospect_notifications']
        
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
        
        # Start event reminder task
        if not self._event_task_started and not self.check_event_reminders.is_running():
            try:
                self.check_event_reminders.start()
                self._event_task_started = True
                logger.info("Event reminder check task started")
            except RuntimeError as e:
                if "threads can only be started once" in str(e):
                    logger.warning("Event task already started, skipping...")
                    self._event_task_started = True
                else:
                    logger.error(f"Failed to start event reminder check task: {e}")
            except Exception as e:
                logger.error(f"Failed to start event reminder check task: {e}")
        elif self.check_event_reminders.is_running():
            logger.info("Event reminder check task already running")
            self._event_task_started = True
        
        # Sync commands
        try:
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
        
        # Start precise reminder system
        try:
            await self.precise_reminders.start()
            await self.precise_reminders.refresh_reminders_from_database()
            logger.info("⏰ Precise reminder system started with 1-second accuracy")
        except Exception as e:
            logger.error(f"Failed to start precise reminder system: {e}")
    
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
    
    @tasks.loop(minutes=1)  # Check every minute for event reminders
    async def check_event_reminders(self):
        """Background task to check for event reminders with precise timing"""
        try:
            # Get events that need reminders sent
            events_needing_reminders = await self.db.get_events_needing_reminders()
            
            for event in events_needing_reminders:
                guild = self.get_guild(event['guild_id'])
                if not guild:
                    continue
                
                # Send reminders to all invited members
                invitations = await self.db.get_event_invitations(event['id'])
                
                for invitation in invitations:
                    member = guild.get_member(invitation['user_id'])
                    if member:
                        try:
                            await self.send_event_reminder_dm(member, event)
                        except Exception as e:
                            logger.error(f"Failed to send event reminder to {member.id}: {e}")
                
                # Mark reminder as sent
                await self.db.mark_reminder_sent(event['id'])
                logger.info(f"Sent reminders for event '{event['event_name']}' (ID: {event['id']})")
                
        except Exception as e:
            logger.error(f"Error checking event reminders: {e}", exc_info=True)
    
    async def send_event_reminder_dm(self, member, event):
        """Send event reminder DM to a member"""
        try:
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
            
        except discord.Forbidden:
            logger.warning(f"Cannot send DM to {member.display_name} ({member.id}) - DMs disabled")
        except Exception as e:
            logger.error(f"Error sending event reminder DM to {member.id}: {e}")
    
    @check_loa_expiration.before_loop
    async def before_check_loa_expiration(self):
        await self.wait_until_ready()
        logger.info("LOA expiration check task is ready to start")
    
    @check_event_reminders.before_loop
    async def before_check_event_reminders(self):
        await self.wait_until_ready()
        logger.info("Event reminder check task is ready to start")

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
