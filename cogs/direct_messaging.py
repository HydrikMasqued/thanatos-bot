import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import Optional, Dict, List
import asyncio
import json
import io

class DirectMessagingSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Store active DM conversations {user_id: guild_id}
        self.active_conversations: Dict[int, int] = {}
        # Store the original sender {user_id: sender_id} 
        self.conversation_senders: Dict[int, int] = {}
    
    def _has_admin_permissions(self, member: discord.Member) -> bool:
        """Check if member has administrator permissions"""
        return member.guild_permissions.administrator
    
    def _has_officer_permissions(self, member: discord.Member, config: dict) -> bool:
        """Check if member has officer permissions"""
        if self._has_admin_permissions(member):
            return True
        
        officer_role_id = config.get('officer_role_id')
        if officer_role_id:
            officer_role = member.guild.get_role(officer_role_id)
            if officer_role and officer_role in member.roles:
                return True
        
        return False
    
    async def _find_user_by_name(self, guild: discord.Guild, search_term: str) -> Optional[discord.Member]:
        """Find a user by display name or username"""
        search_term = search_term.lower()
        
        # First try exact matches
        for member in guild.members:
            if member.display_name.lower() == search_term or member.name.lower() == search_term:
                return member
        
        # Then try partial matches
        for member in guild.members:
            if (search_term in member.display_name.lower() or 
                search_term in member.name.lower()):
                return member
        
        return None
    
    async def _find_role_by_name(self, guild: discord.Guild, search_term: str) -> Optional[discord.Role]:
        """Find a role by name"""
        search_term = search_term.lower()
        
        # First try exact matches
        for role in guild.roles:
            if role.name.lower() == search_term:
                return role
        
        # Then try partial matches
        for role in guild.roles:
            if search_term in role.name.lower() and not role.is_default():
                return role
        
        return None
    
    async def _log_transcript(self, guild_id: int, sender_id: int, recipient_id: int, message: str, 
                            message_type: str = "outbound", recipient_type: str = "user", 
                            role_id: int = None, attachments: List[str] = None):
        """Log message to transcript database"""
        try:
            transcript_data = {
                'guild_id': guild_id,
                'sender_id': sender_id,
                'recipient_id': recipient_id,
                'role_id': role_id,
                'message': message,
                'message_type': message_type,  # 'outbound', 'inbound'
                'recipient_type': recipient_type,  # 'user', 'role'
                'attachments': json.dumps(attachments) if attachments else None,
                'timestamp': datetime.now().isoformat()
            }
            
            # Store in database
            await self.bot.db.log_dm_transcript(
                guild_id=guild_id,
                sender_id=sender_id,
                recipient_id=recipient_id,
                role_id=role_id,
                message=message,
                message_type=message_type,
                recipient_type=recipient_type,
                attachments=json.dumps(attachments) if attachments else None
            )
        except Exception as e:
            print(f"Error logging transcript: {e}")
    
    @app_commands.command(name="dm_user", description="Send a direct message to a user (Admin/Officer only)")
    async def dm_user_command(self, interaction: discord.Interaction, user_identifier: str, message: str):
        """Send a DM to a user by their display name or Discord username"""
        # Check permissions
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config:
            return await interaction.response.send_message(
                "❌ Server configuration not found. Please run `/setup` first.", ephemeral=True
            )
        
        if not self._has_officer_permissions(interaction.user, config):
            return await interaction.response.send_message(
                "❌ This command requires administrator or officer permissions.", ephemeral=True
            )
        
        # Find the user
        target_user = await self._find_user_by_name(interaction.guild, user_identifier)
        
        if not target_user:
            # Try to find by user ID if it's a number
            if user_identifier.isdigit():
                target_user = interaction.guild.get_member(int(user_identifier))
        
        if not target_user:
            return await interaction.response.send_message(
                f"❌ Could not find user matching '{user_identifier}'. Try using their exact display name, username, or user ID.", 
                ephemeral=True
            )
        
        if target_user.bot:
            return await interaction.response.send_message(
                "❌ Cannot send DMs to bots.", ephemeral=True
            )
        
        try:
            # Create DM embed
            dm_embed = discord.Embed(
                title=f"📨 Message from {interaction.guild.name}",
                description=message,
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            dm_embed.set_author(
                name=f"Sent by: {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )
            dm_embed.set_footer(
                text="You can reply to this message and it will be sent back to the server."
            )
            
            # Send the DM
            await target_user.send(embed=dm_embed)
            
            # Store active conversation
            self.active_conversations[target_user.id] = interaction.guild.id
            self.conversation_senders[target_user.id] = interaction.user.id
            
            # Send confirmation
            confirm_embed = discord.Embed(
                title="✅ Message Sent",
                description=f"Successfully sent DM to **{target_user.display_name}** (@{target_user.name})",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            confirm_embed.add_field(
                name="Message Content",
                value=message[:1000] + ("..." if len(message) > 1000 else ""),
                inline=False
            )
            confirm_embed.add_field(
                name="Status",
                value="User can now reply and their messages will be relayed to your configured channel.",
                inline=False
            )
            
            await interaction.response.send_message(embed=confirm_embed, ephemeral=True)
            
            # Log to transcript
            await self._log_transcript(
                guild_id=interaction.guild.id,
                sender_id=interaction.user.id,
                recipient_id=target_user.id,
                message=message,
                message_type="outbound",
                recipient_type="user"
            )
            
            # Log to notification channel if configured
            notification_channel_id = config.get('notification_channel_id')
            if notification_channel_id:
                notification_channel = interaction.guild.get_channel(notification_channel_id)
                if notification_channel:
                    log_embed = discord.Embed(
                        title="📤 DM Sent",
                        description=f"**{interaction.user.display_name}** sent a DM to **{target_user.display_name}**",
                        color=discord.Color.blue(),
                        timestamp=datetime.now()
                    )
                    log_embed.add_field(name="Message", value=message[:500] + ("..." if len(message) > 500 else ""), inline=False)
                    await notification_channel.send(embed=log_embed)
                    
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ Could not send DM to **{target_user.display_name}**. They may have DMs disabled or have blocked the bot.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"❌ Failed to send DM: {str(e)}", ephemeral=True
            )
    
    @app_commands.command(name="dm_search", description="Search for users to send DMs to (Admin/Officer only)")
    async def dm_search_command(self, interaction: discord.Interaction, search_term: str):
        """Search for users by name to send DMs"""
        # Check permissions
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config:
            return await interaction.response.send_message(
                "❌ Server configuration not found. Please run `/setup` first.", ephemeral=True
            )
        
        if not self._has_officer_permissions(interaction.user, config):
            return await interaction.response.send_message(
                "❌ This command requires administrator or officer permissions.", ephemeral=True
            )
        
        # Search for matching users
        search_term_lower = search_term.lower()
        matching_users = []
        
        for member in interaction.guild.members:
            if (not member.bot and 
                (search_term_lower in member.display_name.lower() or 
                 search_term_lower in member.name.lower())):
                matching_users.append(member)
        
        if not matching_users:
            return await interaction.response.send_message(
                f"❌ No users found matching '{search_term}'.", ephemeral=True
            )
        
        # Create search results embed
        embed = discord.Embed(
            title=f"🔍 User Search Results",
            description=f"Found {len(matching_users)} user(s) matching '{search_term}':",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Show up to 10 results
        for i, user in enumerate(matching_users[:10]):
            embed.add_field(
                name=f"{i+1}. {user.display_name}",
                value=f"Username: @{user.name}\nID: {user.id}",
                inline=True
            )
        
        if len(matching_users) > 10:
            embed.set_footer(text=f"Showing first 10 results out of {len(matching_users)} total matches")
        
        # Add usage tip
        embed.add_field(
            name="💡 Usage Tip",
            value="Use `/dm_user <display_name_or_username> <message>` to send a DM",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="dm_active", description="View active DM conversations (Admin/Officer only)")
    async def dm_active_command(self, interaction: discord.Interaction):
        """View currently active DM conversations"""
        # Check permissions
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config:
            return await interaction.response.send_message(
                "❌ Server configuration not found. Please run `/setup` first.", ephemeral=True
            )
        
        if not self._has_officer_permissions(interaction.user, config):
            return await interaction.response.send_message(
                "❌ This command requires administrator or officer permissions.", ephemeral=True
            )
        
        # Get active conversations for this guild
        guild_conversations = [
            user_id for user_id, guild_id in self.active_conversations.items() 
            if guild_id == interaction.guild.id
        ]
        
        if not guild_conversations:
            return await interaction.response.send_message(
                "📭 No active DM conversations.", ephemeral=True
            )
        
        embed = discord.Embed(
            title="💬 Active DM Conversations",
            description=f"Currently tracking {len(guild_conversations)} active conversation(s):",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        for user_id in guild_conversations[:10]:  # Show up to 10
            user = self.bot.get_user(user_id)
            sender_id = self.conversation_senders.get(user_id)
            sender = self.bot.get_user(sender_id) if sender_id else None
            
            if user:
                embed.add_field(
                    name=f"👤 {user.display_name}",
                    value=f"Username: @{user.name}\n" + 
                          (f"Started by: {sender.display_name}" if sender else "Started by: Unknown"),
                    inline=True
                )
        
        embed.set_footer(text="Users in active conversations can reply to the bot and their messages will be relayed.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="dm_end", description="End a DM conversation with a user (Admin/Officer only)")
    async def dm_end_command(self, interaction: discord.Interaction, user_identifier: str):
        """End an active DM conversation"""
        # Check permissions
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config:
            return await interaction.response.send_message(
                "❌ Server configuration not found. Please run `/setup` first.", ephemeral=True
            )
        
        if not self._has_officer_permissions(interaction.user, config):
            return await interaction.response.send_message(
                "❌ This command requires administrator or officer permissions.", ephemeral=True
            )
        
        # Find the user
        target_user = await self._find_user_by_name(interaction.guild, user_identifier)
        
        if not target_user:
            if user_identifier.isdigit():
                target_user = interaction.guild.get_member(int(user_identifier))
        
        if not target_user:
            return await interaction.response.send_message(
                f"❌ Could not find user matching '{user_identifier}'.", ephemeral=True
            )
        
        # Check if conversation exists
        if target_user.id not in self.active_conversations:
            return await interaction.response.send_message(
                f"❌ No active conversation found with **{target_user.display_name}**.", ephemeral=True
            )
        
        # Remove from active conversations
        del self.active_conversations[target_user.id]
        if target_user.id in self.conversation_senders:
            del self.conversation_senders[target_user.id]
        
        # Send confirmation
        embed = discord.Embed(
            title="✅ Conversation Ended",
            description=f"Ended DM conversation with **{target_user.display_name}**",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(
            name="Status",
            value="The user's messages will no longer be relayed to the server.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Optionally notify the user
        try:
            end_embed = discord.Embed(
                title="📨 Conversation Ended",
                description=f"Your conversation with **{interaction.guild.name}** has been ended by an administrator.",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            await target_user.send(embed=end_embed)
        except (discord.Forbidden, discord.HTTPException):
            pass  # Ignore if we can't send the message
    
    @app_commands.command(name="dm_role", description="Send a direct message to all users in a role (Admin/Officer only)")
    async def dm_role_command(self, interaction: discord.Interaction, role_identifier: str, message: str):
        """Send a DM to all users in a role"""
        # Check permissions
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config:
            return await interaction.response.send_message(
                "❌ Server configuration not found. Please run `/setup` first.", ephemeral=True
            )
        
        if not self._has_officer_permissions(interaction.user, config):
            return await interaction.response.send_message(
                "❌ This command requires administrator or officer permissions.", ephemeral=True
            )
        
        # Find the role
        target_role = await self._find_role_by_name(interaction.guild, role_identifier)
        
        if not target_role:
            # Try to find by role ID if it's a number
            if role_identifier.isdigit():
                target_role = interaction.guild.get_role(int(role_identifier))
        
        if not target_role:
            return await interaction.response.send_message(
                f"❌ Could not find role matching '{role_identifier}'. Try using the exact role name or role ID.", 
                ephemeral=True
            )
        
        # Get all members with this role (excluding bots)
        target_members = [member for member in target_role.members if not member.bot]
        
        if not target_members:
            return await interaction.response.send_message(
                f"❌ No users found with the role **{target_role.name}**.", ephemeral=True
            )
        
        # Defer the response since this might take a while
        await interaction.response.defer(ephemeral=True)
        
        successful_sends = 0
        failed_sends = 0
        
        for member in target_members:
            try:
                # Create DM embed
                dm_embed = discord.Embed(
                    title=f"📨 Message from {interaction.guild.name}",
                    description=message,
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                dm_embed.set_author(
                    name=f"Sent by: {interaction.user.display_name}",
                    icon_url=interaction.user.display_avatar.url
                )
                dm_embed.set_footer(
                    text=f"Sent to role: {target_role.name}\nYou can reply to this message and it will be sent back to the server."
                )
                
                # Send the DM
                await member.send(embed=dm_embed)
                
                # Store active conversation
                self.active_conversations[member.id] = interaction.guild.id
                self.conversation_senders[member.id] = interaction.user.id
                
                # Log to transcript
                await self._log_transcript(
                    guild_id=interaction.guild.id,
                    sender_id=interaction.user.id,
                    recipient_id=member.id,
                    role_id=target_role.id,
                    message=message,
                    message_type="outbound",
                    recipient_type="role"
                )
                
                successful_sends += 1
                
                # Small delay to avoid rate limits
                await asyncio.sleep(0.5)
                
            except discord.Forbidden:
                failed_sends += 1
            except discord.HTTPException:
                failed_sends += 1
        
        # Send summary
        summary_embed = discord.Embed(
            title="✅ Role DM Complete",
            description=f"Sent DM to **{target_role.name}** role",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        summary_embed.add_field(
            name="📊 Summary",
            value=f"• **Successful:** {successful_sends}/{len(target_members)} users\n"
                  f"• **Failed:** {failed_sends}/{len(target_members)} users\n"
                  f"• **Total Role Members:** {len(target_members)}",
            inline=False
        )
        summary_embed.add_field(
            name="Message Content",
            value=message[:500] + ("..." if len(message) > 500 else ""),
            inline=False
        )
        summary_embed.add_field(
            name="Status",
            value="Users can now reply and their messages will be relayed to your configured channel.",
            inline=False
        )
        
        await interaction.followup.send(embed=summary_embed, ephemeral=True)
        
        # Log to notification channel if configured
        notification_channel_id = config.get('notification_channel_id')
        if notification_channel_id:
            notification_channel = interaction.guild.get_channel(notification_channel_id)
            if notification_channel:
                log_embed = discord.Embed(
                    title="📤 Role DM Sent",
                    description=f"**{interaction.user.display_name}** sent a DM to **{target_role.name}** role",
                    color=discord.Color.purple(),
                    timestamp=datetime.now()
                )
                log_embed.add_field(
                    name="Results", 
                    value=f"Sent to {successful_sends}/{len(target_members)} members", 
                    inline=True
                )
                log_embed.add_field(
                    name="Message", 
                    value=message[:300] + ("..." if len(message) > 300 else ""), 
                    inline=False
                )
                await notification_channel.send(embed=log_embed)
    
    @app_commands.command(name="transcript_user", description="View DM transcript for a specific user (Admin/Officer only)")
    async def transcript_user_command(self, interaction: discord.Interaction, user_identifier: str, limit: int = 50):
        """View DM transcript history for a specific user"""
        # Check permissions
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config:
            return await interaction.response.send_message(
                "❌ Server configuration not found. Please run `/setup` first.", ephemeral=True
            )
        
        if not self._has_officer_permissions(interaction.user, config):
            return await interaction.response.send_message(
                "❌ This command requires administrator or officer permissions.", ephemeral=True
            )
        
        # Find the user
        target_user = await self._find_user_by_name(interaction.guild, user_identifier)
        
        if not target_user:
            if user_identifier.isdigit():
                target_user = interaction.guild.get_member(int(user_identifier))
        
        if not target_user:
            return await interaction.response.send_message(
                f"❌ Could not find user matching '{user_identifier}'.", ephemeral=True
            )
        
        # Get transcript from database
        try:
            transcripts = await self.bot.db.get_user_transcript(
                guild_id=interaction.guild.id,
                user_id=target_user.id,
                limit=limit
            )
            
            if not transcripts:
                return await interaction.response.send_message(
                    f"❌ No DM transcript found for **{target_user.display_name}**.", ephemeral=True
                )
            
            # Create transcript embed
            embed = discord.Embed(
                title=f"📋 DM Transcript for {target_user.display_name}",
                description=f"Showing last {len(transcripts)} messages (max {limit})",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)
            
            # Add transcript entries
            transcript_text = ""
            for entry in transcripts[-10:]:  # Show last 10 messages in embed
                timestamp = entry.get('timestamp', 'Unknown')
                message_type = entry.get('message_type', 'unknown')
                message = entry.get('message', 'No content')[:100]
                
                direction = "→" if message_type == "outbound" else "←"
                transcript_text += f"`{timestamp}` {direction} {message}\n\n"
            
            if transcript_text:
                embed.add_field(
                    name="Recent Messages",
                    value=transcript_text[:1000] + ("..." if len(transcript_text) > 1000 else ""),
                    inline=False
                )
            
            # Add summary
            outbound_count = len([t for t in transcripts if t.get('message_type') == 'outbound'])
            inbound_count = len([t for t in transcripts if t.get('message_type') == 'inbound'])
            
            embed.add_field(
                name="📊 Summary",
                value=f"• **Total Messages:** {len(transcripts)}\n"
                      f"• **Sent to User:** {outbound_count}\n"
                      f"• **Received from User:** {inbound_count}",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error retrieving transcript: {str(e)}", ephemeral=True
            )
    
    @app_commands.command(name="transcript_search", description="Search DM transcripts by message content (Admin/Officer only)")
    async def transcript_search_command(self, interaction: discord.Interaction, search_term: str, limit: int = 20):
        """Search through DM transcripts for specific content"""
        # Check permissions
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config:
            return await interaction.response.send_message(
                "❌ Server configuration not found. Please run `/setup` first.", ephemeral=True
            )
        
        if not self._has_officer_permissions(interaction.user, config):
            return await interaction.response.send_message(
                "❌ This command requires administrator or officer permissions.", ephemeral=True
            )
        
        try:
            # Search transcripts in database
            results = await self.bot.db.search_transcripts(
                guild_id=interaction.guild.id,
                search_term=search_term,
                limit=limit
            )
            
            if not results:
                return await interaction.response.send_message(
                    f"❌ No transcripts found containing '{search_term}'.", ephemeral=True
                )
            
            # Create results embed
            embed = discord.Embed(
                title=f"🔍 Transcript Search Results",
                description=f"Found {len(results)} message(s) containing '{search_term}'",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Add search results
            for i, result in enumerate(results[:5]):  # Show first 5 results
                user_id = result.get('recipient_id') if result.get('message_type') == 'outbound' else result.get('sender_id')
                user = interaction.guild.get_member(user_id) or self.bot.get_user(user_id)
                username = user.display_name if user else f"User ID: {user_id}"
                
                timestamp = result.get('timestamp', 'Unknown')
                message_type = result.get('message_type', 'unknown')
                message = result.get('message', 'No content')[:200]
                
                direction = "→ Sent to" if message_type == "outbound" else "← Received from"
                
                embed.add_field(
                    name=f"{i+1}. {direction} {username}",
                    value=f"`{timestamp}`\n{message}",
                    inline=False
                )
            
            if len(results) > 5:
                embed.set_footer(text=f"Showing first 5 results out of {len(results)} total matches")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error searching transcripts: {str(e)}", ephemeral=True
            )
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle incoming DMs and relay them to the configured channel"""
        # Ignore messages from bots
        if message.author.bot:
            return
        
        # Only process DMs
        if not isinstance(message.channel, discord.DMChannel):
            return
        
        # Check if this user has an active conversation
        user_id = message.author.id
        if user_id not in self.active_conversations:
            return
        
        guild_id = self.active_conversations[user_id]
        guild = self.bot.get_guild(guild_id)
        
        if not guild:
            # Guild no longer exists, clean up
            del self.active_conversations[user_id]
            if user_id in self.conversation_senders:
                del self.conversation_senders[user_id]
            return
        
        # Get server configuration
        config = await self.bot.db.get_server_config(guild_id)
        if not config:
            return
        
        # Determine which channel to send to (prefer notification channel)
        target_channel_id = (config.get('notification_channel_id') or 
                           config.get('leadership_channel_id'))
        
        if not target_channel_id:
            return
        
        target_channel = guild.get_channel(target_channel_id)
        if not target_channel:
            return
        
        try:
            # Create relay embed
            relay_embed = discord.Embed(
                title="💬 DM Reply Received",
                description=message.content or "*[No text content]*",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            relay_embed.set_author(
                name=f"From: {message.author.display_name} (@{message.author.name})",
                icon_url=message.author.display_avatar.url
            )
            
            # Add original sender info if available
            sender_id = self.conversation_senders.get(user_id)
            if sender_id:
                sender = guild.get_member(sender_id)
                if sender:
                    relay_embed.set_footer(text=f"Originally contacted by: {sender.display_name}")
            
            # Handle attachments
            files_to_send = []
            if message.attachments:
                attachment_info = []
                for attachment in message.attachments:
                    attachment_info.append(f"📎 {attachment.filename}")
                    # Try to download and re-upload small attachments
                    if attachment.size < 8 * 1024 * 1024:  # 8MB limit
                        try:
                            file_data = await attachment.read()
                            files_to_send.append(discord.File(
                                fp=io.BytesIO(file_data), 
                                filename=attachment.filename
                            ))
                        except:
                            attachment_info.append(f"⚠️ Could not relay {attachment.filename}")
                
                if attachment_info:
                    relay_embed.add_field(
                        name="Attachments",
                        value="\n".join(attachment_info[:10]),  # Limit to 10 attachments
                        inline=False
                    )
            
            # Send the relay message
            await target_channel.send(embed=relay_embed, files=files_to_send)
            
            # Send confirmation back to user
            confirm_embed = discord.Embed(
                title="✅ Message Relayed",
                description="Your message has been sent to the server.",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            await message.author.send(embed=confirm_embed)
            
        except discord.HTTPException:
            # If we can't send to the channel, try to notify the user
            try:
                error_embed = discord.Embed(
                    title="❌ Relay Failed",
                    description="Your message could not be relayed to the server. The conversation may have been ended.",
                    color=discord.Color.red()
                )
                await message.author.send(embed=error_embed)
            except:
                pass
            
            # Clean up the conversation
            if user_id in self.active_conversations:
                del self.active_conversations[user_id]
            if user_id in self.conversation_senders:
                del self.conversation_senders[user_id]
    
    @app_commands.command(name="mass_dm", description="Send a direct message to all users in a role (Admin/Officer only) - Alias for dm_role")
    async def mass_dm_command(self, interaction: discord.Interaction, role_identifier: str, message: str):
        """Alias for dm_role command for compatibility with menu systems"""
        await self.dm_role_command(interaction, role_identifier, message)
    
    @app_commands.command(name="transcript_list", description="List all DM transcripts (Admin/Officer only)")
    async def transcript_list_command(self, interaction: discord.Interaction, page: int = 1):
        """List all DM transcripts with pagination"""
        # Check permissions
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config:
            return await interaction.response.send_message(
                "❌ Server configuration not found. Please run `/setup` first.", ephemeral=True
            )
        
        if not self._has_officer_permissions(interaction.user, config):
            return await interaction.response.send_message(
                "❌ This command requires administrator or officer permissions.", ephemeral=True
            )
        
        try:
            # Get recent conversations (this gives us unique user pairs)
            conversations = await self.bot.db.get_recent_dm_conversations(
                guild_id=interaction.guild.id,
                limit=20  # Show 20 conversations per page
            )
            
            if not conversations:
                return await interaction.response.send_message(
                    "📭 No DM transcripts found.", ephemeral=True
                )
            
            # Create list embed
            embed = discord.Embed(
                title="📋 DM Transcript List",
                description=f"Showing recent conversations (Page {page})",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Add conversations to embed
            for i, conv in enumerate(conversations[:10]):  # Show 10 per embed
                # Determine the user involved in the conversation
                user_id = conv.get('recipient_id') if conv.get('message_type') == 'outbound' else conv.get('sender_id')
                user = interaction.guild.get_member(user_id) or self.bot.get_user(user_id)
                username = user.display_name if user else f"User ID: {user_id}"
                
                # Get message info
                created_at = conv.get('created_at', 'Unknown')
                message_type = conv.get('message_type', 'unknown')
                message_preview = conv.get('message', 'No content')[:100]
                recipient_type = conv.get('recipient_type', 'user')
                
                # Activity status
                is_active = user_id in self.active_conversations if user else False
                activity_status = "🟢 Active" if is_active else "⚪ Inactive"
                
                # Direction indicator
                direction = "→ Sent to" if message_type == "outbound" else "← Received from"
                
                # Role info if applicable
                role_info = ""
                if recipient_type == "role" and conv.get('role_id'):
                    role = interaction.guild.get_role(conv.get('role_id'))
                    if role:
                        role_info = f" (via @{role.name})"
                
                embed.add_field(
                    name=f"{i+1}. {username} {activity_status}",
                    value=f"**Last Activity:** `{created_at}`\n"
                          f"**Type:** {direction}{role_info}\n"
                          f"**Preview:** {message_preview}{'...' if len(conv.get('message', '')) > 100 else ''}",
                    inline=False
                )
            
            # Add summary footer
            total_active = len([uid for uid, gid in self.active_conversations.items() if gid == interaction.guild.id])
            embed.set_footer(
                text=f"Total Conversations: {len(conversations)} | Active: {total_active} | "
                     f"Use /transcript_user <username> to view full history"
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error retrieving transcript list: {str(e)}", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(DirectMessagingSystem(bot))
