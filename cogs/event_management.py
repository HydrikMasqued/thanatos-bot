import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
import json
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)

class EventAnalyticsView(discord.ui.View):
    """View for event analytics with export options"""
    
    def __init__(self, bot, analytics: Dict, days: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.analytics = analytics
        self.days = days
    
    @discord.ui.button(label="📊 Export CSV", style=discord.ButtonStyle.primary, emoji="📊")
    async def export_csv(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        try:
            from utils.event_export_utils import EventExportUtils
            
            # Get events data for CSV export
            events = await self.bot.db.get_active_events(interaction.guild.id)
            
            # Filter by date
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=self.days)
            recent_events = []
            for event in events:
                try:
                    event_date = datetime.fromisoformat(event['created_at'].replace('Z', '+00:00'))
                    if event_date >= cutoff_date:
                        recent_events.append(event)
                except:
                    recent_events.append(event)
            
            # Create CSV
            csv_buffer = EventExportUtils.create_attendance_csv(recent_events)
            filename = f"event_attendance_{interaction.guild.name}_{self.days}days_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            await EventExportUtils.send_csv_file(
                interaction, 
                csv_buffer, 
                filename, 
                f"Event attendance data for {interaction.guild.name} ({self.days} days)"
            )
            
        except Exception as e:
            logger.error(f"Error exporting CSV: {e}")
            await interaction.followup.send("❌ Error generating CSV export.", ephemeral=True)
    
    @discord.ui.button(label="📈 Export JSON", style=discord.ButtonStyle.secondary, emoji="📈")
    async def export_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        try:
            from utils.event_export_utils import EventExportUtils
            
            # Create JSON export
            json_buffer = EventExportUtils.create_analytics_json(self.analytics)
            filename = f"event_analytics_{interaction.guild.name}_{self.days}days_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            await EventExportUtils.send_json_file(
                interaction,
                json_buffer,
                filename,
                f"Event analytics for {interaction.guild.name} ({self.days} days)"
            )
            
        except Exception as e:
            logger.error(f"Error exporting JSON: {e}")
            await interaction.followup.send("❌ Error generating JSON export.", ephemeral=True)
    
    @discord.ui.button(label="📋 Text Summary", style=discord.ButtonStyle.secondary, emoji="📋")
    async def text_summary(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            from utils.event_export_utils import EventExportUtils
            
            # Get events for summary
            events = await self.bot.db.get_active_events(interaction.guild.id)
            
            # Filter by date
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=self.days)
            recent_events = []
            for event in events:
                try:
                    event_date = datetime.fromisoformat(event['created_at'].replace('Z', '+00:00'))
                    if event_date >= cutoff_date:
                        recent_events.append(event)
                except:
                    recent_events.append(event)
            
            # Create summary text
            summary_text = EventExportUtils.create_summary_table_text(recent_events)
            
            # Split into chunks if too long
            chunks = [summary_text[i:i+1900] for i in range(0, len(summary_text), 1900)]
            
            for i, chunk in enumerate(chunks):
                embed = discord.Embed(
                    title=f"📋 Event Summary Report {f'(Part {i+1}/{len(chunks)})' if len(chunks) > 1 else ''}",
                    description=f"```{chunk}```",
                    color=discord.Color.gold(),
                    timestamp=datetime.now()
                )
                
                if i == 0:  # Only add footer to first embed
                    embed.set_footer(text=f"Generated for {self.days} day period")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error generating text summary: {e}")
            await interaction.response.send_message("❌ Error generating summary.", ephemeral=True)

class EventManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.reminder_check.start()  # Start the reminder task
        
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.reminder_check.cancel()

    async def _check_officer_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has officer permissions"""
        config = await self.db.get_server_config(interaction.guild.id)
        if not config or not config.get('officer_role_id'):
            await interaction.response.send_message(
                "❌ Officer role not configured. Please ask an administrator to set it up.",
                ephemeral=True
            )
            return False
        
        officer_role = interaction.guild.get_role(config['officer_role_id'])
        if not officer_role or officer_role not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ You need officer permissions to use this command.",
                ephemeral=True
            )
            return False
        return True

    async def _parse_date_time(self, date_str: str, time_str: str = None) -> Optional[datetime]:
        """Parse date and time strings using natural language processing"""
        try:
            # If both date and time are provided, combine them
            if time_str and time_str.strip():
                combined_text = f"{date_str.strip()} {time_str.strip()}"
            else:
                combined_text = date_str.strip()
            
            # Use the enhanced time parser for natural language parsing
            parsed_datetime = self.bot.time_parser.parse_natural_datetime(combined_text)
            
            if parsed_datetime:
                return parsed_datetime
            
            # Fallback to old parsing method for compatibility
            return await self._parse_date_time_legacy(date_str, time_str)
                
        except Exception as e:
            logger.error(f"Error parsing natural date/time '{date_str}' '{time_str}': {e}")
            return None
    
    async def _parse_date_time_legacy(self, date_str: str, time_str: str = None) -> Optional[datetime]:
        """Legacy date/time parsing for fallback compatibility"""
        try:
            # Try different date formats
            date_formats = [
                "%Y-%m-%d",      # 2024-12-25
                "%m/%d/%Y",      # 12/25/2024
                "%m-%d-%Y",      # 12-25-2024
                "%d/%m/%Y",      # 25/12/2024
                "%d-%m-%Y"       # 25-12-2024
            ]
            
            parsed_date = None
            for fmt in date_formats:
                try:
                    parsed_date = datetime.strptime(date_str, fmt).date()
                    break
                except ValueError:
                    continue
            
            if not parsed_date:
                return None
            
            # Parse time if provided
            if time_str:
                time_formats = [
                    "%H:%M",         # 14:30
                    "%I:%M %p",      # 2:30 PM
                    "%I:%M%p",       # 2:30PM
                    "%H:%M:%S",      # 14:30:00
                ]
                
                parsed_time = None
                for fmt in time_formats:
                    try:
                        parsed_time = datetime.strptime(time_str.upper(), fmt).time()
                        break
                    except ValueError:
                        continue
                
                if not parsed_time:
                    return None
                
                return datetime.combine(parsed_date, parsed_time)
            else:
                # Default to noon if no time specified
                return datetime.combine(parsed_date, datetime.min.time().replace(hour=12))
                
        except Exception as e:
            logger.error(f"Error parsing legacy date/time '{date_str}' '{time_str}': {e}")
            return None

    @app_commands.command(name="event", description="Create an event and invite role members automatically")
    @app_commands.describe(
        name="Event name",
        time="When is the event? (e.g. 'today 8pm', 'tomorrow 3:30', 'friday 7pm', 'jan 15 8pm')",
        description="Event description",
        role="Role to invite to the event (all members will be automatically RSVP'd as 'Yes')",
        send_dms="Whether to send DM invitations to all invited members (default: No)"
    )
    async def event(
        self,
        interaction: discord.Interaction,
        name: str,
        time: str,
        description: str,
        role: discord.Role,
        send_dms: bool = False
    ):
        """Create a new event and invite role members automatically"""
        if not await self._check_officer_permissions(interaction):
            return

        # Defer response since we might need to send DMs
        await interaction.response.defer()

        # Parse the date and time
        event_datetime = await self._parse_date_time(time)
        if not event_datetime:
            await interaction.followup.send(
                "❌ Invalid date/time format. Try natural language like:\n"
                "• **Today**: `today 8pm`, `tonight`, `today at 3:30pm`\n"
                "• **Tomorrow**: `tomorrow 7pm`, `tomorrow at 2:30`\n"
                "• **Day Names**: `friday 8pm`, `next monday 3pm`, `saturday at noon`\n"
                "• **Specific Dates**: `jan 15 8pm`, `march 3rd 7:30pm`, `12/25 6pm`\n"
                "• **Traditional**: `2024-12-25`, `12/25/2024 14:30`",
                ephemeral=True
            )
            return

        # Check if date is in the future
        if event_datetime <= datetime.now():
            await interaction.followup.send(
                "❌ Event date must be in the future.",
                ephemeral=True
            )
            return

        try:
            # Create the event
            event_id = await self.db.create_event(
                guild_id=interaction.guild.id,
                event_name=name,
                description=description,
                category="General",
                event_date=event_datetime,
                created_by_id=interaction.user.id,
                reminder_hours_before=24
            )

            # Invite all role members automatically
            invited_users = []
            failed_invites = []
            
            for member in role.members:
                if not member.bot:  # Skip bots
                    success = await self.db.invite_user_to_event(
                        event_id=event_id,
                        guild_id=interaction.guild.id,
                        user_id=member.id,
                        invited_by_id=interaction.user.id,
                        invitation_method="event_creation",
                        role_id=role.id
                    )
                    if success:
                        invited_users.append(member)
                    else:
                        failed_invites.append(member)

            # Send DMs if requested
            dm_sent_count = 0
            dm_failed_count = 0
            
            if send_dms and invited_users:
                # Create event embed for DMs
                dm_embed = discord.Embed(
                    title=f"📅 Event Invitation: {name}",
                    description=description,
                    color=discord.Color.blue(),
                    timestamp=event_datetime
                )
                
                dm_embed.add_field(name="📅 Date & Time", value=event_datetime.strftime("%Y-%m-%d %H:%M"), inline=True)
                dm_embed.add_field(name="🎭 Role", value=role.name, inline=True)
                dm_embed.add_field(
                    name="💬 Your RSVP",
                    value=f"You've been automatically RSVP'd as **Yes**\nUse `/rsvp {event_id} <yes/no/maybe>` in {interaction.guild.name} to change",
                    inline=False
                )
                dm_embed.set_footer(text=f"Event ID: {event_id} | From {interaction.guild.name}")
                
                # Send DMs to invited users
                for member in invited_users:
                    try:
                        await member.send(embed=dm_embed)
                        await self.db.mark_dm_sent(event_id, member.id)
                        dm_sent_count += 1
                        await asyncio.sleep(0.5)  # Rate limit protection
                    except Exception as e:
                        logger.error(f"Failed to send DM to {member.display_name}: {e}")
                        dm_failed_count += 1

            # Create confirmation embed
            embed = discord.Embed(
                title="🎉 Event Created & Users Invited!",
                description=f"**{name}** has been created and users invited!",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="📅 Date & Time", value=event_datetime.strftime("%Y-%m-%d %H:%M"), inline=True)
            embed.add_field(name="🎭 Role Invited", value=role.name, inline=True)
            embed.add_field(name="🆔 Event ID", value=str(event_id), inline=True)
            
            embed.add_field(name="📝 Description", value=description, inline=False)
            
            # Invitation summary
            invite_summary = f"✅ **{len(invited_users)}** members automatically RSVP'd as **Yes**"
            if failed_invites:
                invite_summary += f"\n⚠️ {len(failed_invites)} failed/skipped"
            embed.add_field(name="📬 Invitations", value=invite_summary, inline=False)
            
            # DM summary if requested
            if send_dms:
                dm_summary = f"📨 **{dm_sent_count}** DMs sent successfully"
                if dm_failed_count > 0:
                    dm_summary += f"\n❌ {dm_failed_count} DMs failed"
                embed.add_field(name="Direct Messages", value=dm_summary, inline=False)
            elif invited_users:
                embed.add_field(name="💡 Tip", value="Use `/send_event_dms` to send DM invitations later", inline=False)
            
            embed.set_footer(text=f"Created by {interaction.user.display_name}")

            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            await interaction.followup.send(
                "❌ An error occurred while creating the event. Please try again.",
                ephemeral=True
            )

    @app_commands.command(name="invite_to_event", description="Invite users or roles to an event (automatically RSVPs them as 'Yes')")
    @app_commands.describe(
        event_id="Event ID to invite to",
        users="Users to invite (mention them) - they will be automatically RSVP'd as 'Yes'",
        role="Role to invite (optional) - all role members will be automatically RSVP'd as 'Yes'"
    )
    async def invite_to_event(
        self,
        interaction: discord.Interaction,
        event_id: int,
        users: Optional[str] = None,
        role: Optional[discord.Role] = None
    ):
        """Invite users or roles to an event"""
        if not await self._check_officer_permissions(interaction):
            return

        # Get the event
        event = await self.db.get_event_by_id(event_id)
        if not event or event['guild_id'] != interaction.guild.id:
            await interaction.response.send_message(
                "❌ Event not found or not in this server.",
                ephemeral=True
            )
            return

        if not event['is_active']:
            await interaction.response.send_message(
                "❌ This event is no longer active.",
                ephemeral=True
            )
            return

        invited_users = []
        failed_invites = []

        try:
            # Handle role invitations
            if role:
                for member in role.members:
                    if not member.bot:  # Skip bots
                        success = await self.db.invite_user_to_event(
                            event_id=event_id,
                            guild_id=interaction.guild.id,
                            user_id=member.id,
                            invited_by_id=interaction.user.id,
                            invitation_method="role_invite",
                            role_id=role.id
                        )
                        if success:
                            invited_users.append(member)
                        else:
                            failed_invites.append(f"{member.display_name} (already invited)")

            # Handle individual user invitations
            if users:
                # Parse user mentions
                import re
                user_mentions = re.findall(r'<@!?(\d+)>', users)
                
                for user_id_str in user_mentions:
                    user_id = int(user_id_str)
                    member = interaction.guild.get_member(user_id)
                    
                    if member and not member.bot:
                        success = await self.db.invite_user_to_event(
                            event_id=event_id,
                            guild_id=interaction.guild.id,
                            user_id=user_id,
                            invited_by_id=interaction.user.id,
                            invitation_method="direct_invite"
                        )
                        if success:
                            invited_users.append(member)
                        else:
                            failed_invites.append(f"{member.display_name} (already invited)")
                    else:
                        failed_invites.append(f"User ID {user_id} (not found or is bot)")

            if not invited_users and not failed_invites:
                await interaction.response.send_message(
                    "❌ No users specified. Please mention users or select a role.",
                    ephemeral=True
                )
                return

            # Create response embed
            embed = discord.Embed(
                title="📬 Event Invitations Sent",
                description=f"Invitations for **{event['event_name']}**\n✅ All invited users have been automatically RSVP'd as **'Yes'**",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )

            if invited_users:
                user_list = ", ".join([user.display_name for user in invited_users[:10]])
                if len(invited_users) > 10:
                    user_list += f" and {len(invited_users) - 10} more"
                embed.add_field(
                    name=f"✅ Successfully Invited ({len(invited_users)})",
                    value=user_list,
                    inline=False
                )

            if failed_invites:
                fail_list = ", ".join(failed_invites[:5])
                if len(failed_invites) > 5:
                    fail_list += f" and {len(failed_invites) - 5} more"
                embed.add_field(
                    name=f"⚠️ Failed/Skipped ({len(failed_invites)})",
                    value=fail_list,
                    inline=False
                )

            embed.set_footer(text=f"Event ID: {event_id}")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error sending event invitations: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while sending invitations.",
                ephemeral=True
            )

    @app_commands.command(name="rsvp", description="Respond to an event invitation or change your existing response")
    @app_commands.describe(
        event_id="Event ID to RSVP to",
        response="Your response (yes, no, or maybe) - will override any previous response",
        notes="Optional notes about your response"
    )
    @app_commands.choices(response=[
        app_commands.Choice(name="Yes - I'll attend", value="yes"),
        app_commands.Choice(name="No - I can't attend", value="no"),
        app_commands.Choice(name="Maybe - I'm unsure", value="maybe")
    ])
    async def rsvp(
        self,
        interaction: discord.Interaction,
        event_id: int,
        response: str,
        notes: Optional[str] = None
    ):
        """RSVP to an event"""
        # Get the event
        event = await self.db.get_event_by_id(event_id)
        if not event or event['guild_id'] != interaction.guild.id:
            await interaction.response.send_message(
                "❌ Event not found or not in this server.",
                ephemeral=True
            )
            return

        if not event['is_active']:
            await interaction.response.send_message(
                "❌ This event is no longer active.",
                ephemeral=True
            )
            return

        try:
            # Record the RSVP
            await self.db.record_rsvp(
                event_id=event_id,
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                response=response,
                notes=notes
            )

            # Response emojis
            response_emojis = {
                'yes': '✅',
                'no': '❌',
                'maybe': '❔'
            }

            embed = discord.Embed(
                title=f"{response_emojis.get(response, '📝')} RSVP Recorded",
                description=f"Your response to **{event['event_name']}** has been recorded.",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )

            embed.add_field(name="Response", value=response.capitalize(), inline=True)
            embed.add_field(name="Event Date", value=event['event_date'], inline=True)
            
            if notes:
                embed.add_field(name="Notes", value=notes, inline=False)

            embed.set_footer(text=f"Event ID: {event_id}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error recording RSVP: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while recording your RSVP.",
                ephemeral=True
            )

    @app_commands.command(name="event_details", description="View details of an event")
    @app_commands.describe(event_id="Event ID to view details for")
    async def event_details(self, interaction: discord.Interaction, event_id: int):
        """View details of an event"""
        # Get the event
        event = await self.db.get_event_by_id(event_id)
        if not event or event['guild_id'] != interaction.guild.id:
            await interaction.response.send_message(
                "❌ Event not found or not in this server.",
                ephemeral=True
            )
            return

        # Get RSVPs
        rsvps = await self.db.get_event_rsvps(event_id)
        
        # Create main embed
        embed = discord.Embed(
            title=f"📅 {event['event_name']}",
            description=event['description'],
            color=discord.Color.blue(),
            timestamp=datetime.fromisoformat(event['created_at'].replace('Z', '+00:00'))
        )

        # Event details
        embed.add_field(name="📅 Date & Time", value=event['event_date'], inline=True)
        embed.add_field(name="📋 Category", value=event['category'], inline=True)
        embed.add_field(name="🆔 Event ID", value=str(event_id), inline=True)

        if event.get('location'):
            embed.add_field(name="📍 Location", value=event['location'], inline=True)
        
        if event.get('max_attendees'):
            embed.add_field(name="👥 Max Attendees", value=str(event['max_attendees']), inline=True)

        # RSVP counts
        yes_count = len(rsvps['yes'])
        no_count = len(rsvps['no'])
        maybe_count = len(rsvps['maybe'])
        total_responses = yes_count + no_count + maybe_count

        rsvp_text = f"✅ Yes: {yes_count}\n❌ No: {no_count}\n❔ Maybe: {maybe_count}\n📊 Total: {total_responses}"
        embed.add_field(name="RSVP Summary", value=rsvp_text, inline=True)

        # Creator info
        if event.get('created_by_name'):
            embed.add_field(name="👤 Created by", value=event['created_by_name'], inline=True)

        # Status
        status = "🟢 Active" if event['is_active'] else "🔴 Inactive"
        embed.add_field(name="Status", value=status, inline=True)

        embed.set_footer(text=f"Created on")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="event_rsvps", description="View RSVPs for an event")
    @app_commands.describe(event_id="Event ID to view RSVPs for")
    async def event_rsvps(self, interaction: discord.Interaction, event_id: int):
        """View RSVPs for an event"""
        if not await self._check_officer_permissions(interaction):
            return

        # Get the event
        event = await self.db.get_event_by_id(event_id)
        if not event or event['guild_id'] != interaction.guild.id:
            await interaction.response.send_message(
                "❌ Event not found or not in this server.",
                ephemeral=True
            )
            return

        # Get RSVPs
        rsvps = await self.db.get_event_rsvps(event_id)

        embed = discord.Embed(
            title=f"📋 RSVPs for {event['event_name']}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        # Format RSVP lists
        for response_type, emoji in [('yes', '✅'), ('no', '❌'), ('maybe', '❔')]:
            response_list = rsvps.get(response_type, [])
            if response_list:
                names = []
                for rsvp in response_list[:10]:  # Show first 10
                    name = rsvp.get('discord_name', f"User {rsvp['user_id']}")
                    if rsvp.get('rank'):
                        name += f" ({rsvp['rank']})"
                    names.append(name)
                
                value = "\n".join(names)
                if len(response_list) > 10:
                    value += f"\n... and {len(response_list) - 10} more"
                
                embed.add_field(
                    name=f"{emoji} {response_type.capitalize()} ({len(response_list)})",
                    value=value or "None",
                    inline=True
                )
            else:
                embed.add_field(
                    name=f"{emoji} {response_type.capitalize()} (0)",
                    value="None",
                    inline=True
                )

        embed.set_footer(text=f"Event ID: {event_id}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="list_events", description="List all active events")
    @app_commands.describe(category="Filter by category (optional)")
    async def list_events(self, interaction: discord.Interaction, category: Optional[str] = None):
        """List all active events"""
        try:
            events = await self.db.get_active_events(interaction.guild.id)
            
            if category:
                events = [e for e in events if e['category'].lower() == category.lower()]

            if not events:
                message = f"No active events found"
                if category:
                    message += f" in category '{category}'"
                message += "."
                
                await interaction.response.send_message(message, ephemeral=True)
                return

            embed = discord.Embed(
                title="📅 Active Events",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )

            if category:
                embed.description = f"Events in category: **{category}**"

            # Group events by category
            categories = {}
            for event in events:
                cat = event['category']
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(event)

            for cat, cat_events in categories.items():
                event_list = []
                for event in cat_events[:5]:  # Show first 5 per category
                    date_str = event['event_date']
                    rsvp_count = (event.get('yes_count', 0) or 0)
                    event_list.append(
                        f"**{event['event_name']}** (ID: {event['id']})\n"
                        f"📅 {date_str} | ✅ {rsvp_count} attending"
                    )
                
                value = "\n\n".join(event_list)
                if len(cat_events) > 5:
                    value += f"\n\n... and {len(cat_events) - 5} more"
                
                embed.add_field(
                    name=f"📋 {cat} ({len(cat_events)})",
                    value=value,
                    inline=False
                )

            embed.set_footer(text="Use /event_details <id> for more information")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error listing events: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while retrieving events.",
                ephemeral=True
            )

    @app_commands.command(name="send_event_dms", description="Send DM invitations for an event")
    @app_commands.describe(event_id="Event ID to send DMs for")
    async def send_event_dms(self, interaction: discord.Interaction, event_id: int):
        """Send DM invitations for an event"""
        if not await self._check_officer_permissions(interaction):
            return

        await interaction.response.defer()

        try:
            # Get the event
            event = await self.db.get_event_by_id(event_id)
            if not event or event['guild_id'] != interaction.guild.id:
                await interaction.followup.send(
                    "❌ Event not found or not in this server.",
                    ephemeral=True
                )
                return

            # Get event invitations
            invitations = await self.db.get_event_invitations(event_id)
            
            if not invitations:
                await interaction.followup.send(
                    "❌ No invitations found for this event. Use `/invite_to_event` first.",
                    ephemeral=True
                )
                return

            # Filter out users who already received DMs
            pending_dms = [inv for inv in invitations if not inv.get('dm_sent', False)]
            
            if not pending_dms:
                await interaction.followup.send(
                    "✅ All invited users have already received DM invitations.",
                    ephemeral=True
                )
                return

            # Create event embed for DMs
            embed = discord.Embed(
                title=f"📅 Event Invitation: {event['event_name']}",
                description=event['description'],
                color=discord.Color.blue(),
                timestamp=datetime.fromisoformat(event['event_date'])
            )

            embed.add_field(name="📅 Date & Time", value=event['event_date'], inline=True)
            embed.add_field(name="📋 Category", value=event['category'], inline=True)
            
            if event.get('location'):
                embed.add_field(name="📍 Location", value=event['location'], inline=True)

            embed.add_field(
                name="💬 How to RSVP",
                value=f"Use `/rsvp {event_id} <yes/no/maybe>` in {interaction.guild.name}",
                inline=False
            )

            embed.set_footer(text=f"Event ID: {event_id} | From {interaction.guild.name}")

            # Send DMs
            sent_count = 0
            failed_count = 0
            failed_users = []

            for invitation in pending_dms:
                try:
                    user = self.bot.get_user(invitation['user_id'])
                    if not user:
                        user = await self.bot.fetch_user(invitation['user_id'])
                    
                    if user:
                        await user.send(embed=embed)
                        await self.db.mark_dm_sent(event_id, invitation['user_id'])
                        sent_count += 1
                        
                        # Small delay to avoid rate limits
                        await asyncio.sleep(0.5)
                    else:
                        failed_count += 1
                        failed_users.append(f"User ID {invitation['user_id']}")

                except Exception as e:
                    logger.error(f"Failed to send DM to user {invitation['user_id']}: {e}")
                    failed_count += 1
                    failed_users.append(invitation.get('discord_name', f"User {invitation['user_id']}"))

            # Create response embed
            response_embed = discord.Embed(
                title="📬 Event DM Invitations Sent",
                description=f"Results for **{event['event_name']}**",
                color=discord.Color.green() if failed_count == 0 else discord.Color.orange(),
                timestamp=datetime.now()
            )

            response_embed.add_field(
                name="✅ Successfully Sent",
                value=str(sent_count),
                inline=True
            )

            if failed_count > 0:
                fail_list = ", ".join(failed_users[:5])
                if len(failed_users) > 5:
                    fail_list += f" and {len(failed_users) - 5} more"
                
                response_embed.add_field(
                    name="❌ Failed",
                    value=str(failed_count),
                    inline=True
                )
                response_embed.add_field(
                    name="Failed Users",
                    value=fail_list,
                    inline=False
                )

            response_embed.set_footer(text=f"Event ID: {event_id}")
            await interaction.followup.send(embed=response_embed)

        except Exception as e:
            logger.error(f"Error sending event DMs: {e}")
            await interaction.followup.send(
                "❌ An error occurred while sending DM invitations.",
                ephemeral=True
            )

    @app_commands.command(name="event_analytics", description="View event analytics")
    @app_commands.describe(days="Number of days to analyze (default: 30)")
    async def event_analytics(self, interaction: discord.Interaction, days: Optional[int] = 30):
        """View event analytics"""
        if not await self._check_officer_permissions(interaction):
            return

        try:
            analytics = await self.db.get_event_analytics(interaction.guild.id, days)

            # Use the new enhanced formatting
            from utils.event_export_utils import EventExportUtils
            embed = EventExportUtils.format_attendance_summary(analytics, days)
            
            # Add export options view
            view = EventAnalyticsView(self.bot, analytics, days)
            
            await interaction.response.send_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error getting event analytics: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while retrieving analytics.",
                ephemeral=True
            )
    
    @app_commands.command(name="export_event_data", description="Export event attendance data to CSV")
    @app_commands.describe(
        days="Number of days to include in export (default: 30)",
        format="Export format (csv or json)"
    )
    @app_commands.choices(format=[
        app_commands.Choice(name="CSV (Excel compatible)", value="csv"),
        app_commands.Choice(name="JSON (for analysis)", value="json")
    ])
    async def export_event_data(
        self, 
        interaction: discord.Interaction, 
        days: Optional[int] = 30,
        format: Optional[str] = "csv"
    ):
        """Export event attendance data"""
        if not await self._check_officer_permissions(interaction):
            return
        
        await interaction.response.defer()
        
        try:
            from utils.event_export_utils import EventExportUtils
            
            if format == "csv":
                # Get events data
                events = await self.db.get_active_events(interaction.guild.id)
                
                # Filter by date if needed
                from datetime import datetime, timedelta
                cutoff_date = datetime.now() - timedelta(days=days)
                recent_events = []
                for event in events:
                    try:
                        event_date = datetime.fromisoformat(event['created_at'].replace('Z', '+00:00'))
                        if event_date >= cutoff_date:
                            recent_events.append(event)
                    except:
                        recent_events.append(event)  # Include if we can't parse date
                
                # Create CSV
                csv_buffer = EventExportUtils.create_attendance_csv(recent_events)
                filename = f"event_attendance_{interaction.guild.name}_{days}days_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                
                await EventExportUtils.send_csv_file(
                    interaction, 
                    csv_buffer, 
                    filename, 
                    f"Event attendance data for {interaction.guild.name} ({days} days)"
                )
                
            elif format == "json":
                # Get analytics
                analytics = await self.db.get_event_analytics(interaction.guild.id, days)
                
                # Create JSON
                json_buffer = EventExportUtils.create_analytics_json(analytics)
                filename = f"event_analytics_{interaction.guild.name}_{days}days_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                
                await EventExportUtils.send_json_file(
                    interaction,
                    json_buffer,
                    filename,
                    f"Event analytics for {interaction.guild.name} ({days} days)"
                )
        
        except Exception as e:
            logger.error(f"Error exporting event data: {e}")
            await interaction.followup.send(
                "❌ An error occurred while exporting data.",
                ephemeral=True
            )

    @tasks.loop(minutes=30)  # Check every 30 minutes
    async def reminder_check(self):
        """Check for events that need reminders sent"""
        try:
            events = await self.db.get_events_needing_reminders()
            
            for event in events:
                try:
                    guild = self.bot.get_guild(event['guild_id'])
                    if not guild:
                        continue

                    # Get event invitations
                    invitations = await self.db.get_event_invitations(event['id'])
                    
                    if not invitations:
                        continue

                    # Create reminder embed
                    embed = discord.Embed(
                        title=f"⏰ Event Reminder: {event['event_name']}",
                        description=f"This event starts in {event['reminder_hours_before']} hours!",
                        color=discord.Color.orange(),
                        timestamp=datetime.fromisoformat(event['event_date'])
                    )

                    embed.add_field(name="📅 Date & Time", value=event['event_date'], inline=True)
                    embed.add_field(name="📋 Category", value=event['category'], inline=True)
                    
                    if event.get('location'):
                        embed.add_field(name="📍 Location", value=event['location'], inline=True)

                    embed.add_field(name="📝 Description", value=event['description'], inline=False)
                    
                    # Check your RSVP status
                    embed.add_field(
                        name="💬 RSVP Status",
                        value=f"Use `/rsvp {event['id']} <yes/no/maybe>` to update your response",
                        inline=False
                    )

                    embed.set_footer(text=f"Event ID: {event['id']} | From {guild.name}")

                    # Send reminders to all invited users
                    sent_count = 0
                    for invitation in invitations:
                        try:
                            user = self.bot.get_user(invitation['user_id'])
                            if not user:
                                user = await self.bot.fetch_user(invitation['user_id'])
                            
                            if user:
                                await user.send(embed=embed)
                                sent_count += 1
                                await asyncio.sleep(0.5)  # Rate limit protection

                        except Exception as e:
                            logger.error(f"Failed to send reminder to user {invitation['user_id']}: {e}")

                    # Mark reminder as sent
                    await self.db.mark_reminder_sent(event['id'])
                    
                    logger.info(f"Sent reminders for event '{event['event_name']}' to {sent_count} users")

                except Exception as e:
                    logger.error(f"Error processing reminder for event {event['id']}: {e}")

        except Exception as e:
            logger.error(f"Error in reminder check task: {e}")

    @reminder_check.before_loop
    async def before_reminder_check(self):
        """Wait until the bot is ready"""
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(EventManagement(bot))
