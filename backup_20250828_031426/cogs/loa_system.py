import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import asyncio
import io
import aiosqlite

class LOAModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Submit Leave of Absence (LOA)")
        
        # Duration input
        self.duration = discord.ui.TextInput(
            label="Duration",
            placeholder="e.g., 2 weeks, 3 days, 5h, 1 month...",
            max_length=100,
            required=True
        )
        self.add_item(self.duration)
        
        # Reason input
        self.reason = discord.ui.TextInput(
            label="Reason for LOA",
            placeholder="Brief explanation for your leave...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True
        )
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Get the bot instance
        bot = interaction.client
        
        # Check if user already has an active LOA
        existing_loa = await bot.db.get_active_loa(interaction.guild.id, interaction.user.id)
        if existing_loa:
            embed = discord.Embed(
                title="❌ LOA Already Active",
                description="You already have an active LOA. Please contact an officer to modify or cancel your existing LOA.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        try:
            # Parse the duration
            start_time = datetime.now()
            end_time, normalized_duration = bot.time_parser.parse_duration(
                self.duration.value, start_time
            )
            
            # Create LOA record in database
            loa_id = await bot.db.create_loa_record(
                interaction.guild.id,
                interaction.user.id,
                normalized_duration,
                self.reason.value,
                start_time,
                end_time
            )
            
            # Update member record and LOA status
            await bot.db.add_or_update_member(
                interaction.guild.id,
                interaction.user.id,
                interaction.user.display_name
            )
            await bot.db.update_member_loa_status(
                interaction.guild.id,
                interaction.user.id,
                True
            )
            
            # Get server configuration for notifications
            config = await bot.db.get_server_config(interaction.guild.id)
            
            # Create confirmation embed
            embed = discord.Embed(
                title="✅ LOA Submitted Successfully",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Duration", value=normalized_duration, inline=True)
            embed.add_field(name="End Date", value=f"<t:{int(end_time.timestamp())}:F>", inline=True)
            embed.add_field(name="Reason", value=self.reason.value[:500] + "..." if len(self.reason.value) > 500 else self.reason.value, inline=False)
            embed.set_footer(text="Your LOA has been recorded and relevant parties have been notified.")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Send notifications using the notification manager
            loa_data = {
                'duration': normalized_duration,
                'reason': self.reason.value,
                'start_time': start_time,
                'end_time': end_time
            }
            await interaction.client.loa_notifications.notify_loa_started(
                interaction.guild.id, interaction.user, loa_data
            )
            
        except ValueError as e:
            embed = discord.Embed(
                title="❌ Invalid Duration Format",
                description=f"Could not parse duration '{self.duration.value}'. Please use formats like:\n"
                           f"• `5s` or `5 seconds`\n"
                           f"• `30m` or `30 minutes`\n"
                           f"• `2h` or `2 hours`\n"
                           f"• `3d` or `3 days`\n"
                           f"• `2w` or `2 weeks`\n"
                           f"• `1mo` or `1 month`\n"
                           f"• `1y` or `1 year`\n\n"
                           f"**Error:** {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Submitting LOA",
                description=f"An error occurred while processing your LOA: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _send_notifications(self, interaction, config, duration, reason, start_time, end_time):
        """Send notifications to configured roles and users"""
        if not config:
            return
        
        # Create notification embed
        embed = discord.Embed(
            title="📋 New LOA Submitted",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(
            name="Member",
            value=f"{interaction.user.mention} ({interaction.user.display_name})",
            inline=False
        )
        embed.add_field(name="Duration", value=duration, inline=True)
        embed.add_field(name="End Date", value=f"<t:{int(end_time.timestamp())}:F>", inline=True)
        embed.add_field(name="Reason", value=reason[:500] + "..." if len(reason) > 500 else reason, inline=False)
        embed.set_footer(text="LOA will be automatically tracked and notifications sent when expired.")
        
        # Notify role in channel
        if config.get('officer_role_id') and config.get('notification_channel_id'):
            try:
                role = interaction.guild.get_role(config['officer_role_id'])
                channel = interaction.guild.get_channel(config['notification_channel_id'])
                if role and channel:
                    await channel.send(f"{role.mention}", embed=embed)
            except Exception as e:
                print(f"Error sending role notification: {e}")
        
        # Send DM notifications to all configured users
        dm_users = await interaction.client.db.get_dm_users(interaction.guild.id)
        if dm_users:
            for user_id in dm_users:
                try:
                    user = interaction.client.get_user(user_id)
                    if user:
                        # Create a new DM embed with same content
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
                        # Add server field
                        dm_embed.add_field(
                            name="Server", 
                            value=interaction.guild.name, 
                            inline=True
                        )
                        await user.send(embed=dm_embed)
                except Exception as e:
                    print(f"Error sending DM notification to user {user_id}: {e}")

class LOAVerificationView(discord.ui.View):
    def __init__(self, loa_id: int, member: discord.Member):
        super().__init__(timeout=300)  # 5 minute timeout
        self.loa_id = loa_id
        self.member = member
    
    @discord.ui.button(label="Confirm Return", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm_return(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user has officer permissions
        bot = interaction.client
        config = await bot.db.get_server_config(interaction.guild.id)
        
        if not config or not config.get('officer_role_id'):
            return await interaction.response.send_message(
                "❌ Officer role not configured.", ephemeral=True
            )
        
        officer_role = interaction.guild.get_role(config['officer_role_id'])
        if not officer_role or officer_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "❌ You don't have permission to verify LOA returns.", ephemeral=True
            )
        
        # End the LOA
        await bot.db.end_loa(self.loa_id)
        
        # Send return notification
        await interaction.client.loa_notifications.notify_loa_ended(
            interaction.guild.id, self.member
        )
        
        # Update the original message
        embed = discord.Embed(
            title="✅ LOA Return Confirmed",
            description=f"{self.member.mention} has been confirmed as returned by {interaction.user.mention}.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="Extend LOA", style=discord.ButtonStyle.grey, emoji="⏰")
    async def extend_loa(self, interaction: discord.Interaction, button: discord.ui.Button):
        # This could open another modal for extension
        await interaction.response.send_message(
            "To extend an LOA, please have the member submit a new LOA request or contact an administrator.",
            ephemeral=True
        )

class LOASystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    def _generate_loa_table(self, loas: list, guild_name: str) -> str:
        """Generate an ASCII table for active LOAs suitable for Notepad."""
        lines = []
        lines.append(f"ACTIVE LOAS - {guild_name.upper()}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 100)
        lines.append("")
        # Column widths
        # NAME 22, USERNAME 16, DURATION 12, ENDS 20, STATUS 14, REASON 28
        lines.append("+" + "-"*24 + "+" + "-"*18 + "+" + "-"*14 + "+" + "-"*22 + "+" + "-"*16 + "+" + "-"*30 + "+")
        lines.append(f"| {'NAME':<22} | {'USERNAME':<16} | {'DURATION':<12} | {'ENDS':<20} | {'STATUS':<14} | {'REASON':<28} |")
        lines.append("+" + "="*24 + "+" + "="*18 + "+" + "="*14 + "+" + "="*22 + "+" + "="*16 + "+" + "="*30 + "+")
        
        for loa in loas:
            name = loa.get('discord_name', 'Unknown')
            username = loa.get('discord_username', 'N/A')
            duration = loa.get('duration', '')
            reason = loa.get('reason', '')
            # Truncate fields
            if len(name) > 22:
                name = name[:19] + '...'
            if len(username) > 16:
                username = username[:13] + '...'
            if len(duration) > 12:
                duration = duration[:9] + '...'
            if len(reason) > 28:
                reason = reason[:25] + '...'
            # Parse end time
            try:
                end_val = loa.get('end_time')
                if isinstance(end_val, str):
                    if 'T' in end_val:
                        end_dt = datetime.fromisoformat(end_val.replace('Z', '+00:00'))
                    else:
                        end_dt = datetime.strptime(end_val, '%Y-%m-%d %H:%M:%S')
                else:
                    end_dt = end_val or datetime.now()
            except Exception:
                end_dt = datetime.now()
            ends = end_dt.strftime('%Y-%m-%d %H:%M')
            # Status remaining
            try:
                remaining = self.bot.time_parser.format_time_remaining(end_dt)
            except Exception:
                remaining = 'N/A'
            lines.append(f"| {name:<22} | {username:<16} | {duration:<12} | {ends:<20} | {remaining:<14} | {reason:<28} |")
        lines.append("+" + "-"*24 + "+" + "-"*18 + "+" + "-"*14 + "+" + "-"*22 + "+" + "-"*16 + "+" + "-"*30 + "+")
        return "\n".join(lines)
    
    @app_commands.command(name="loa", description="Submit a Leave of Absence request")
    async def loa_command(self, interaction: discord.Interaction):
        """Main LOA command that opens the modal form"""
        modal = LOAModal()
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="loa_status", description="Check your current LOA status")
    async def loa_status(self, interaction: discord.Interaction, member: discord.Member = None):
        """Check LOA status for yourself or another member"""
        target_member = member or interaction.user
        
        # Get active LOA
        loa = await self.bot.db.get_active_loa(interaction.guild.id, target_member.id)
        
        if not loa:
            embed = discord.Embed(
                title="📋 LOA Status",
                description=f"{target_member.display_name} does not have an active LOA.",
                color=discord.Color.blue()
            )
        else:
            # Calculate time remaining
            try:
                # Handle different datetime formats from database
                if isinstance(loa['end_time'], str):
                    if 'T' in loa['end_time']:
                        # ISO format
                        end_time = datetime.fromisoformat(loa['end_time'].replace('Z', '+00:00'))
                    else:
                        # Simple format
                        end_time = datetime.strptime(loa['end_time'], '%Y-%m-%d %H:%M:%S')
                else:
                    # Already a datetime object
                    end_time = loa['end_time']
            except (ValueError, TypeError) as e:
                print(f"Error parsing end_time: {e}")
                end_time = datetime.now()
            
            remaining = self.bot.time_parser.format_time_remaining(end_time)
            
            embed = discord.Embed(
                title="📋 Active LOA",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Member", value=target_member.display_name, inline=True)
            embed.add_field(name="Duration", value=loa['duration'], inline=True)
            embed.add_field(name="Status", value=remaining, inline=True)
            embed.add_field(name="Reason", value=loa['reason'][:500] + "..." if len(loa['reason']) > 500 else loa['reason'], inline=False)
            # Handle start time parsing
            try:
                if isinstance(loa['start_time'], str):
                    if 'T' in loa['start_time']:
                        start_time = datetime.fromisoformat(loa['start_time'].replace('Z', '+00:00'))
                    else:
                        start_time = datetime.strptime(loa['start_time'], '%Y-%m-%d %H:%M:%S')
                else:
                    start_time = loa['start_time']
                start_timestamp = int(start_time.timestamp())
            except (ValueError, TypeError) as e:
                print(f"Error parsing start_time: {e}")
                start_timestamp = int(datetime.now().timestamp())
            
            embed.add_field(name="Started", value=f"<t:{start_timestamp}:F>", inline=True)
            embed.add_field(name="Ends", value=f"<t:{int(end_time.timestamp())}:F>", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="loa_list", description="List all active LOAs (Officers only)")
    async def loa_list(self, interaction: discord.Interaction):
        """List all active LOAs - officers only. Outputs a table file for Notepad."""
        await interaction.response.defer(ephemeral=True)
        
        # Check permissions
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config or not config.get('officer_role_id'):
            return await interaction.followup.send(
                "❌ Officer role not configured.", ephemeral=True
            )
        
        officer_role = interaction.guild.get_role(config['officer_role_id'])
        if not officer_role or officer_role not in interaction.user.roles:
            return await interaction.followup.send(
                "❌ This command is only available to officers.", ephemeral=True
            )
        
        # Get all active LOAs
        import aiosqlite
        conn = await self.bot.db._get_shared_connection()
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute('''
            SELECT l.*, m.discord_name, m.discord_username
            FROM loa_records l
            JOIN members m ON l.guild_id = m.guild_id AND l.user_id = m.user_id
            WHERE l.guild_id = ? AND l.is_active = TRUE AND l.is_expired = FALSE
            ORDER BY l.end_time ASC
        ''', (interaction.guild.id,))
        rows = await cursor.fetchall()
        active_loas = [dict(r) for r in rows]
        
        if not active_loas:
            return await interaction.followup.send(
                embed=discord.Embed(
                    title="📋 Active LOAs",
                    description="No active LOAs found.",
                    color=discord.Color.blue()
                ),
                ephemeral=True
            )
        
        # Generate LOA table file
        content = self._generate_loa_table(active_loas, interaction.guild.name)
        file_content = io.StringIO(content)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file = discord.File(file_content, filename=f"loa_list_{timestamp}.txt")
        
        await interaction.followup.send(
            content=f"📋 **Active LOAs Table** - {len(active_loas)} record(s)",
            file=file,
            ephemeral=True
        )
    
    @app_commands.command(name="loa_cancel", description="Cancel your active LOA")
    async def loa_cancel(self, interaction: discord.Interaction):
        """Cancel user's active LOA"""
        # Get active LOA
        loa = await self.bot.db.get_active_loa(interaction.guild.id, interaction.user.id)
        
        if not loa:
            embed = discord.Embed(
                title="❌ No Active LOA",
                description="You don't have an active LOA to cancel.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # End the LOA
        await self.bot.db.end_loa(loa['id'])
        
        # Send return notification
        await self.bot.loa_notifications.notify_loa_ended(
            interaction.guild.id, interaction.user
        )
        
        embed = discord.Embed(
            title="✅ LOA Cancelled",
            description="Your LOA has been cancelled successfully.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(LOASystem(bot))
