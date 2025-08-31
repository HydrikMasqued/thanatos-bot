import discord
from discord.ext import commands
from datetime import datetime
from typing import Optional, List
import logging

# Set up logger for this module
logger = logging.getLogger(__name__)

class LOANotificationManager:
    """Manages LOA notifications across servers and channels"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def send_loa_notification(self, guild_id: int, user: discord.Member, 
                                  notification_type: str, loa_data: dict = None):
        """
        Send LOA notification to configured channels and roles
        
        Args:
            guild_id: Guild ID where LOA change occurred
            user: Discord member whose LOA status changed
            notification_type: 'started', 'ended', or 'expired'
            loa_data: LOA record data if available
        """
        try:
            # Get server config
            config = await self.bot.db.get_server_config(guild_id)
            if not config:
                return
            
            # Update membership database first
            await self._update_membership_status(guild_id, user, notification_type)
            
            # Create notification embed
            embed = await self._create_notification_embed(user, notification_type, loa_data)
            
            # Get guilds to notify
            guilds_to_notify = await self._get_notification_guilds(guild_id, config)
            
            # Send notifications to all relevant guilds
            for target_guild_id in guilds_to_notify:
                await self._send_guild_notification(target_guild_id, embed, user)
            
            # Send DM notification to configured user
            await self._send_dm_notification(guild_id, embed, user)
                
        except Exception as e:
            logger.error(f"Error sending LOA notification for user {user.id} in guild {guild_id}: {e}")
    
    async def _update_membership_status(self, guild_id: int, user: discord.Member, notification_type: str):
        """Update membership database based on LOA status change"""
        try:
            # Determine new LOA status
            is_on_loa = notification_type in ['started']
            
            # Update member's LOA status in database
            await self.bot.db.update_member_loa_status(guild_id, user.id, is_on_loa)
            
            # Update member's general status
            status = 'LOA' if is_on_loa else 'Active'
            await self.bot.db.add_or_update_member(
                guild_id, user.id, user.display_name, 
                discord_username=user.name, status=status
            )
            
            logger.info(f"Updated membership status for {user.display_name} (ID: {user.id}) - LOA: {is_on_loa}")
            
        except Exception as e:
            logger.error(f"Error updating membership status for user {user.id}: {e}")
    
    async def _create_notification_embed(self, user: discord.Member, 
                                       notification_type: str, loa_data: dict = None) -> discord.Embed:
        """Create embed for LOA notification"""
        
        if notification_type == 'started':
            title = "🟠 Member on Leave of Absence"
            color = discord.Color.orange()
            description = f"**{user.display_name}** has started a Leave of Absence"
        elif notification_type == 'ended':
            title = "🟢 Member Returned from LOA"
            color = discord.Color.green()
            description = f"**{user.display_name}** has returned from Leave of Absence"
        elif notification_type == 'expired':
            title = "⏰ LOA Expired"
            color = discord.Color.red()
            description = f"**{user.display_name}**'s Leave of Absence has expired"
        else:
            title = "📊 Membership Update"
            color = discord.Color.blue()
            description = f"**{user.display_name}**'s membership status has been updated"
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now()
        )
        
        # Add user info
        embed.add_field(
            name="Member",
            value=f"{user.mention} (`@{user.name}`)",
            inline=True
        )
        
        # Add LOA details if available
        if loa_data:
            if loa_data.get('duration'):
                embed.add_field(
                    name="Duration",
                    value=loa_data['duration'],
                    inline=True
                )
            
            if loa_data.get('reason'):
                embed.add_field(
                    name="Reason",
                    value=loa_data['reason'][:100] + ("..." if len(loa_data['reason']) > 100 else ""),
                    inline=False
                )
            
            if loa_data.get('end_time'):
                end_time = loa_data['end_time']
                if isinstance(end_time, str):
                    # Parse datetime string if needed
                    try:
                        from dateutil import parser
                        end_time = parser.parse(end_time)
                    except:
                        pass
                
                if hasattr(end_time, 'strftime'):
                    embed.add_field(
                        name="Expected Return" if notification_type == 'started' else "Was Expected",
                        value=end_time.strftime('%Y-%m-%d %H:%M UTC'),
                        inline=True
                    )
        
        # Add membership impact notice
        if notification_type == 'started':
            embed.add_field(
                name="📊 Membership Impact",
                value="Member status updated to **LOA** in membership database",
                inline=False
            )
        elif notification_type in ['ended', 'expired']:
            embed.add_field(
                name="📊 Membership Impact",
                value="Member status updated to **Active** in membership database",
                inline=False
            )
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"User ID: {user.id}")
        
        return embed
    
    async def _get_notification_guilds(self, origin_guild_id: int, config: dict) -> List[int]:
        """Get list of guild IDs that should receive notifications"""
        guilds_to_notify = [origin_guild_id]  # Always notify origin guild
        
        # Check if cross-server notifications are enabled
        if config.get('cross_server_notifications', False):
            # Find all guilds with LOA notification channels configured
            for guild in self.bot.guilds:
                if guild.id == origin_guild_id:
                    continue
                
                guild_config = await self.bot.db.get_server_config(guild.id)
                if guild_config and guild_config.get('loa_notification_channel_id'):
                    guilds_to_notify.append(guild.id)
        
        return guilds_to_notify
    
    async def _send_guild_notification(self, guild_id: int, embed: discord.Embed, user: discord.Member):
        """Send notification to a specific guild"""
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return
            
            config = await self.bot.db.get_server_config(guild_id)
            if not config:
                return
            
            # Get notification channel
            channel_id = config.get('loa_notification_channel_id')
            if not channel_id:
                return
            
            channel = guild.get_channel(channel_id)
            if not channel:
                logger.warning(f"LOA notification channel {channel_id} not found in guild {guild_id}")
                return
            
            # Prepare mention for notification role
            mention_text = ""
            if config.get('loa_notification_role_id'):
                role = guild.get_role(config['loa_notification_role_id'])
                if role:
                    mention_text = f"{role.mention} "
            
            # Send notification
            await channel.send(content=mention_text, embed=embed)
            logger.info(f"Sent LOA notification to guild {guild_id}, channel {channel_id}")
            
        except Exception as e:
            logger.error(f"Error sending notification to guild {guild_id}: {e}")
    
    async def _send_dm_notification(self, guild_id: int, embed: discord.Embed, user: discord.Member):
        """Send DM notifications to all configured users"""
        try:
            dm_users = await self.bot.db.get_dm_users(guild_id)
            if not dm_users:
                return
            
            # Get guild for embed info
            guild = self.bot.get_guild(guild_id)
            
            # Send to each configured DM user
            for user_id in dm_users:
                try:
                    dm_user = self.bot.get_user(user_id)
                    if not dm_user:
                        logger.warning(f"DM user {user_id} not found")
                        continue
                    
                    # Create DM-specific embed with guild info
                    dm_embed = discord.Embed(
                        title=embed.title,
                        description=embed.description,
                        color=embed.color,
                        timestamp=embed.timestamp
                    )
                    
                    # Copy fields from original embed
                    for field in embed.fields:
                        dm_embed.add_field(
                            name=field.name,
                            value=field.value,
                            inline=field.inline
                        )
                    
                    # Add guild information
                    if guild:
                        dm_embed.add_field(
                            name="🏰 Server",
                            value=guild.name,
                            inline=True
                        )
                    
                    dm_embed.set_thumbnail(url=embed.thumbnail.url if embed.thumbnail else None)
                    dm_embed.set_footer(text=f"From: {guild.name if guild else 'Unknown Server'} | {embed.footer.text if embed.footer else ''}")
                    
                    # Send DM
                    await dm_user.send(embed=dm_embed)
                    logger.info(f"Sent LOA DM notification to user {dm_user.id}")
                    
                except discord.Forbidden:
                    logger.warning(f"Cannot send DM to user {user_id} - DMs may be disabled")
                except Exception as e:
                    logger.error(f"Error sending DM notification to user {user_id}: {e}")
            
        except Exception as e:
            logger.error(f"Error sending DM notifications: {e}")
    
    async def notify_loa_started(self, guild_id: int, user: discord.Member, loa_data: dict):
        """Notify when a member starts LOA"""
        await self.send_loa_notification(guild_id, user, 'started', loa_data)
    
    async def notify_loa_ended(self, guild_id: int, user: discord.Member, loa_data: dict = None):
        """Notify when a member ends LOA"""
        await self.send_loa_notification(guild_id, user, 'ended', loa_data)
    
    async def notify_loa_expired(self, guild_id: int, user: discord.Member, loa_data: dict):
        """Notify when LOA expires automatically"""
        await self.send_loa_notification(guild_id, user, 'expired', loa_data)
