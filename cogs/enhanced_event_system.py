"""
Enhanced Event Management System
Features interactive DM invitations, flexible invitee selection, and comprehensive attendance tracking.
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
import json
import re
from typing import Optional, List, Dict, Any, Union
import logging

logger = logging.getLogger(__name__)

class EventInvitationView(discord.ui.View):
    """Interactive view for event RSVP responses via DM"""
    
    def __init__(self, event_id: int, event_data: Dict, bot):
        super().__init__(timeout=None)  # Never timeout for persistent RSVPs
        self.event_id = event_id
        self.event_data = event_data
        self.bot = bot
        
        # Set custom IDs for persistence across bot restarts
        self.yes_button.custom_id = f"rsvp_yes_{event_id}"
        self.no_button.custom_id = f"rsvp_no_{event_id}"
        self.maybe_button.custom_id = f"rsvp_maybe_{event_id}"
        self.details_button.custom_id = f"rsvp_details_{event_id}"
    
    @discord.ui.button(label="✅ Yes - I'll attend", style=discord.ButtonStyle.success, emoji="✅", row=0)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_rsvp(interaction, "yes", "✅")
    
    @discord.ui.button(label="❌ No - Can't attend", style=discord.ButtonStyle.danger, emoji="❌", row=0)  
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_rsvp(interaction, "no", "❌")
    
    @discord.ui.button(label="🤔 Maybe - Unsure", style=discord.ButtonStyle.secondary, emoji="🤔", row=0)
    async def maybe_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_rsvp(interaction, "maybe", "🤔")
    
    @discord.ui.button(label="📅 Event Details", style=discord.ButtonStyle.primary, emoji="📅", row=1)
    async def details_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._show_event_details(interaction)
    
    async def _handle_rsvp(self, interaction: discord.Interaction, response: str, emoji: str):
        """Handle RSVP response"""
        try:
            # Record the RSVP in database
            await self.bot.db.record_rsvp(
                event_id=self.event_id,
                guild_id=self.event_data['guild_id'],
                user_id=interaction.user.id,
                response=response,
                notes=f"Responded via DM at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # Create confirmation embed
            embed = discord.Embed(
                title=f"{emoji} RSVP Confirmed",
                description=f"Your response for **{self.event_data['event_name']}** has been recorded!",
                color=discord.Color.green() if response == "yes" else 
                      discord.Color.red() if response == "no" else 
                      discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="📅 Event", value=self.event_data['event_name'], inline=True)
            embed.add_field(name="📍 Response", value=response.title(), inline=True)
            embed.add_field(name="🕐 Event Time", value=self.event_data['event_date'], inline=True)
            
            # Update buttons to show current response
            await self._update_buttons_for_response(response)
            
            await interaction.response.edit_message(embed=embed, view=self)
            
            # Notify event creator
            await self._notify_event_creator(interaction.user, response)
            
        except Exception as e:
            logger.error(f"Error handling RSVP: {e}")
            await interaction.response.send_message(
                "❌ Sorry, there was an error recording your RSVP. Please try again.",
                ephemeral=True
            )
    
    async def _update_buttons_for_response(self, response: str):
        """Update button styles to show current response"""
        # Reset all buttons to secondary
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id.startswith("rsvp_"):
                item.style = discord.ButtonStyle.secondary
        
        # Highlight the selected response
        if response == "yes":
            self.yes_button.style = discord.ButtonStyle.success
        elif response == "no":
            self.no_button.style = discord.ButtonStyle.danger
        elif response == "maybe":
            self.maybe_button.style = discord.ButtonStyle.primary
    
    async def _show_event_details(self, interaction: discord.Interaction):
        """Show full event details"""
        embed = discord.Embed(
            title=f"📅 {self.event_data['event_name']}",
            description=self.event_data['description'],
            color=discord.Color.blue(),
            timestamp=datetime.fromisoformat(self.event_data['event_date'])
        )
        
        embed.add_field(name="📅 Date & Time", value=self.event_data['event_date'], inline=True)
        embed.add_field(name="📋 Category", value=self.event_data['category'], inline=True)
        embed.add_field(name="🆔 Event ID", value=str(self.event_id), inline=True)
        
        if self.event_data.get('location'):
            embed.add_field(name="📍 Location", value=self.event_data['location'], inline=True)
        
        if self.event_data.get('max_attendees'):
            embed.add_field(name="👥 Max Attendees", value=str(self.event_data['max_attendees']), inline=True)
        
        # Get current RSVP counts
        try:
            rsvps = await self.bot.db.get_event_rsvps(self.event_id)
            yes_count = len(rsvps.get('yes', []))
            no_count = len(rsvps.get('no', []))
            maybe_count = len(rsvps.get('maybe', []))
            total_responses = yes_count + no_count + maybe_count
            
            rsvp_text = f"✅ Yes: {yes_count}\n❌ No: {no_count}\n🤔 Maybe: {maybe_count}\n📊 Total: {total_responses}"
            embed.add_field(name="RSVP Summary", value=rsvp_text, inline=True)
        except:
            embed.add_field(name="RSVP Summary", value="Loading...", inline=True)
        
        embed.set_footer(text=f"Event ID: {self.event_id}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _notify_event_creator(self, user: discord.User, response: str):
        """Notify the event creator of the RSVP response"""
        try:
            creator_id = self.event_data.get('created_by_id')
            if not creator_id:
                return
            
            creator = self.bot.get_user(creator_id)
            if not creator:
                creator = await self.bot.fetch_user(creator_id)
            
            if creator:
                embed = discord.Embed(
                    title="📬 New RSVP Response",
                    description=f"**{user.display_name}** responded to your event!",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(name="📅 Event", value=self.event_data['event_name'], inline=True)
                embed.add_field(name="👤 User", value=user.display_name, inline=True)
                embed.add_field(name="📍 Response", value=f"{response.title()}", inline=True)
                embed.add_field(name="🕐 Event Time", value=self.event_data['event_date'], inline=False)
                
                embed.set_thumbnail(url=user.display_avatar.url)
                embed.set_footer(text=f"Event ID: {self.event_id}")
                
                await creator.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Error notifying event creator: {e}")

class InviteeSelectionModal(discord.ui.Modal):
    """Modal for selecting event invitees flexibly"""
    
    def __init__(self, event_id: int, bot):
        super().__init__(title="Select Event Invitees")
        self.event_id = event_id
        self.bot = bot
        
        # Invitee input field
        self.invitees_input = discord.ui.TextInput(
            label="Who to invite?",
            placeholder="Enter usernames, display names, user IDs, or @mentions...\nSeparate multiple entries with commas or new lines",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=True
        )
        self.add_item(self.invitees_input)
        
        # Optional message field
        self.message_input = discord.ui.TextInput(
            label="Custom Invitation Message (Optional)",
            placeholder="Add a personal message to include with the invitation...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False
        )
        self.add_item(self.message_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            # Get event data
            event = await self.bot.db.get_event_by_id(self.event_id)
            if not event:
                await interaction.followup.send("❌ Event not found.", ephemeral=True)
                return
            
            # Parse invitees
            invitees_text = self.invitees_input.value
            custom_message = self.message_input.value.strip() if self.message_input.value else None
            
            # Find users using flexible matching
            found_users, failed_searches = await self._find_users(interaction, invitees_text)
            
            if not found_users:
                await interaction.followup.send(
                    "❌ No valid users found. Please check your input and try again.",
                    ephemeral=True
                )
                return
            
            # Send invitations
            await self._send_invitations(interaction, event, found_users, custom_message)
            
            # Report results
            await self._send_results(interaction, found_users, failed_searches)
            
        except Exception as e:
            logger.error(f"Error in invitee selection: {e}")
            await interaction.followup.send(
                "❌ An error occurred while processing invitations.",
                ephemeral=True
            )
    
    async def _find_users(self, interaction: discord.Interaction, invitees_text: str) -> tuple:
        """Find users from flexible input"""
        found_users = []
        failed_searches = []
        
        # Split input by commas or newlines
        entries = re.split(r'[,\n]+', invitees_text.strip())
        
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
            
            user = await self._find_single_user(interaction, entry)
            if user:
                if user not in found_users:  # Avoid duplicates
                    found_users.append(user)
            else:
                failed_searches.append(entry)
        
        return found_users, failed_searches
    
    async def _find_single_user(self, interaction: discord.Interaction, search_term: str) -> Optional[discord.Member]:
        """Find a single user from various search methods"""
        # Method 1: User mention <@123> or <@!123>
        mention_match = re.match(r'<@!?(\d+)>', search_term)
        if mention_match:
            try:
                user_id = int(mention_match.group(1))
                return interaction.guild.get_member(user_id)
            except:
                pass
        
        # Method 2: User ID (pure numbers)
        if search_term.isdigit():
            try:
                user_id = int(search_term)
                return interaction.guild.get_member(user_id)
            except:
                pass
        
        # Method 3: Exact display name match
        for member in interaction.guild.members:
            if member.display_name.lower() == search_term.lower():
                return member
        
        # Method 4: Exact username match
        for member in interaction.guild.members:
            if member.name.lower() == search_term.lower():
                return member
        
        # Method 5: Partial display name match
        for member in interaction.guild.members:
            if search_term.lower() in member.display_name.lower():
                return member
        
        # Method 6: Partial username match
        for member in interaction.guild.members:
            if search_term.lower() in member.name.lower():
                return member
        
        return None
    
    async def _send_invitations(self, interaction: discord.Interaction, event: Dict, users: List[discord.Member], custom_message: str = None):
        """Send interactive DM invitations to users"""
        sent_count = 0
        
        for user in users:
            if user.bot:  # Skip bots
                continue
            
            try:
                # Record invitation in database
                await self.bot.db.invite_user_to_event(
                    event_id=self.event_id,
                    guild_id=interaction.guild.id,
                    user_id=user.id,
                    invited_by_id=interaction.user.id,
                    invitation_method="custom_selection"
                )
                
                # Create invitation embed
                embed = discord.Embed(
                    title=f"📅 Event Invitation: {event['event_name']}",
                    description=event['description'],
                    color=discord.Color.blue(),
                    timestamp=datetime.fromisoformat(event['event_date'])
                )
                
                embed.add_field(name="📅 Date & Time", value=event['event_date'], inline=True)
                embed.add_field(name="📋 Category", value=event['category'], inline=True)
                embed.add_field(name="👤 Invited by", value=interaction.user.display_name, inline=True)
                
                if event.get('location'):
                    embed.add_field(name="📍 Location", value=event['location'], inline=True)
                
                if custom_message:
                    embed.add_field(name="💬 Personal Message", value=custom_message, inline=False)
                
                embed.add_field(
                    name="🎯 How to Respond",
                    value="Use the buttons below to RSVP!\nYou can change your response anytime.",
                    inline=False
                )
                
                embed.set_footer(text=f"Event ID: {self.event_id} | From {interaction.guild.name}")
                
                # Create interactive view
                view = EventInvitationView(self.event_id, event, self.bot)
                
                # Send DM
                await user.send(embed=embed, view=view)
                await self.bot.db.mark_dm_sent(self.event_id, user.id)
                sent_count += 1
                
                # Rate limit protection
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Failed to send invitation to {user.display_name}: {e}")
    
    async def _send_results(self, interaction: discord.Interaction, found_users: List[discord.Member], failed_searches: List[str]):
        """Send results summary"""
        embed = discord.Embed(
            title="📬 Invitation Results",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        # Successfully invited
        if found_users:
            user_list = [f"• {user.display_name}" for user in found_users[:20]]
            if len(found_users) > 20:
                user_list.append(f"• ... and {len(found_users) - 20} more")
            
            embed.add_field(
                name=f"✅ Successfully Invited ({len(found_users)})",
                value="\n".join(user_list),
                inline=False
            )
        
        # Failed searches
        if failed_searches:
            fail_list = [f"• `{term}`" for term in failed_searches[:10]]
            if len(failed_searches) > 10:
                fail_list.append(f"• ... and {len(failed_searches) - 10} more")
            
            embed.add_field(
                name=f"❌ Not Found ({len(failed_searches)})",
                value="\n".join(fail_list),
                inline=False
            )
        
        embed.add_field(
            name="💡 Next Steps",
            value="• Invitees will receive interactive DM invitations\n"
                  "• You'll be notified when they respond\n"
                  "• Use `/event_rsvps` to view all responses\n"
                  "• Use `/event_details` to see event summary",
            inline=False
        )
        
        embed.set_footer(text=f"Event ID: {self.event_id}")
        
        await interaction.followup.send(embed=embed)

class EventCreationModal(discord.ui.Modal):
    """Enhanced event creation modal"""
    
    def __init__(self, bot):
        super().__init__(title="Create New Event")
        self.bot = bot
        
        # Event name
        self.name_input = discord.ui.TextInput(
            label="Event Name",
            placeholder="Enter the event name...",
            max_length=100,
            required=True
        )
        self.add_item(self.name_input)
        
        # Event time
        self.time_input = discord.ui.TextInput(
            label="Date & Time",
            placeholder="e.g. 'tomorrow 8pm', 'friday 3pm', 'jan 15 7:30pm'",
            max_length=100,
            required=True
        )
        self.add_item(self.time_input)
        
        # Event description
        self.description_input = discord.ui.TextInput(
            label="Event Description",
            placeholder="Describe the event details, requirements, etc...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True
        )
        self.add_item(self.description_input)
        
        # Event location (optional)
        self.location_input = discord.ui.TextInput(
            label="Location (Optional)",
            placeholder="Where will this event take place?",
            max_length=200,
            required=False
        )
        self.add_item(self.location_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            # Parse the date and time
            event_datetime = await self._parse_date_time(self.time_input.value)
            if not event_datetime:
                await interaction.followup.send(
                    "❌ Invalid date/time format. Try natural language like:\n"
                    "• **Today**: `today 8pm`, `tonight`, `today at 3:30pm`\n"
                    "• **Tomorrow**: `tomorrow 7pm`, `tomorrow at 2:30`\n"
                    "• **Day Names**: `friday 8pm`, `next monday 3pm`, `saturday at noon`\n"
                    "• **Specific Dates**: `jan 15 8pm`, `march 3rd 7:30pm`, `12/25 6pm`",
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
            
            # Create the event
            event_id = await self.bot.db.create_event(
                guild_id=interaction.guild.id,
                event_name=self.name_input.value,
                description=self.description_input.value,
                category="General",
                event_date=event_datetime,
                location=self.location_input.value.strip() if self.location_input.value else None,
                created_by_id=interaction.user.id,
                reminder_hours_before=24
            )
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Event Created Successfully!",
                description=f"**{self.name_input.value}** has been created.",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="📅 Date & Time", value=event_datetime.strftime("%Y-%m-%d %H:%M"), inline=True)
            embed.add_field(name="🆔 Event ID", value=str(event_id), inline=True)
            embed.add_field(name="👤 Created by", value=interaction.user.display_name, inline=True)
            
            embed.add_field(name="📝 Description", value=self.description_input.value, inline=False)
            
            if self.location_input.value:
                embed.add_field(name="📍 Location", value=self.location_input.value, inline=False)
            
            embed.add_field(
                name="🚀 Next Steps",
                value=f"• Use the **Invite People** button to select invitees\n"
                      f"• Or use `/invite_to_event {event_id}` command\n"
                      f"• View responses with `/event_rsvps {event_id}`\n"
                      f"• Get event details with `/event_details {event_id}`",
                inline=False
            )
            
            # Create view with invite button
            view = EventCreatedView(event_id, self.bot)
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            await interaction.followup.send(
                "❌ An error occurred while creating the event. Please try again.",
                ephemeral=True
            )
    
    async def _parse_date_time(self, date_str: str) -> Optional[datetime]:
        """Parse date and time using the bot's time parser"""
        try:
            if hasattr(self.bot, 'time_parser'):
                return self.bot.time_parser.parse_natural_datetime(date_str)
            else:
                # Fallback parsing - basic implementation
                return await self._parse_date_time_fallback(date_str)
        except Exception as e:
            logger.error(f"Error parsing date/time '{date_str}': {e}")
            return None
    
    async def _parse_date_time_fallback(self, date_str: str) -> Optional[datetime]:
        """Fallback date/time parsing"""
        # This is a simple implementation - you may want to enhance this
        import dateutil.parser as parser
        try:
            return parser.parse(date_str, fuzzy=True)
        except:
            return None

class EventCreatedView(discord.ui.View):
    """View shown after event creation"""
    
    def __init__(self, event_id: int, bot):
        super().__init__(timeout=300)
        self.event_id = event_id
        self.bot = bot
    
    @discord.ui.button(label="👥 Invite People", style=discord.ButtonStyle.primary, emoji="👥")
    async def invite_people(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = InviteeSelectionModal(self.event_id, self.bot)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📊 View Event", style=discord.ButtonStyle.secondary, emoji="📊")
    async def view_event(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Get event details command
        events_cog = self.bot.get_cog('EnhancedEventSystem')
        if events_cog:
            await events_cog.event_details.callback(events_cog, interaction, self.event_id)

class EnhancedEventSystem(commands.Cog):
    """Enhanced Event Management System with interactive features"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        
        # Add persistent views for RSVP buttons
        self.bot.add_view(EventInvitationView(0, {}, bot), message_id=None)  # Template for persistence
    
    async def cog_load(self):
        """Load persistent views on startup"""
        logger.info("Enhanced Event System loaded")
    
    async def _check_officer_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has officer permissions"""
        from utils.contribution_audit_helpers import ContributionAuditHelpers
        return await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot)
    
    @app_commands.command(name="create_event_interactive", description="Create an event with interactive setup")
    async def create_event_interactive(self, interaction: discord.Interaction):
        """Create an event using interactive modal"""
        if not await self._check_officer_permissions(interaction):
            from utils.contribution_audit_helpers import ContributionAuditHelpers
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **Event Creation** requires Officer permissions."
            )
            return
        
        modal = EventCreationModal(self.bot)
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="invite_people", description="Invite people to an event with flexible selection")
    @app_commands.describe(event_id="Event ID to invite people to")
    async def invite_people(self, interaction: discord.Interaction, event_id: int):
        """Invite people to an event using flexible selection"""
        if not await self._check_officer_permissions(interaction):
            from utils.contribution_audit_helpers import ContributionAuditHelpers
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **Event Invitations** require Officer permissions."
            )
            return
        
        # Check if event exists
        event = await self.bot.db.get_event_by_id(event_id)
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
        
        modal = InviteeSelectionModal(event_id, self.bot)
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="event_attendance_report", description="Generate comprehensive attendance report")
    @app_commands.describe(
        event_id="Event ID to generate report for (optional - shows recent events if not specified)",
        days="Number of days to include in historical analysis (default: 30)"
    )
    async def event_attendance_report(
        self, 
        interaction: discord.Interaction, 
        event_id: Optional[int] = None,
        days: Optional[int] = 30
    ):
        """Generate comprehensive attendance report"""
        if not await self._check_officer_permissions(interaction):
            from utils.contribution_audit_helpers import ContributionAuditHelpers
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **Attendance Reports** require Officer permissions."
            )
            return
        
        await interaction.response.defer()
        
        try:
            if event_id:
                # Single event report
                await self._generate_single_event_report(interaction, event_id)
            else:
                # Historical attendance analysis
                await self._generate_historical_report(interaction, days)
                
        except Exception as e:
            logger.error(f"Error generating attendance report: {e}")
            await interaction.followup.send(
                "❌ An error occurred while generating the report.",
                ephemeral=True
            )
    
    async def _generate_single_event_report(self, interaction: discord.Interaction, event_id: int):
        """Generate detailed report for a single event"""
        # Get event details
        event = await self.bot.db.get_event_by_id(event_id)
        if not event or event['guild_id'] != interaction.guild.id:
            await interaction.followup.send("❌ Event not found or not in this server.", ephemeral=True)
            return
        
        # Get RSVPs
        rsvps = await self.bot.db.get_event_rsvps(event_id)
        
        # Create comprehensive report
        embed = discord.Embed(
            title=f"📊 Attendance Report: {event['event_name']}",
            description=f"Comprehensive analysis for Event ID: {event_id}",
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )
        
        # Event details
        embed.add_field(name="📅 Event Date", value=event['event_date'], inline=True)
        embed.add_field(name="📋 Category", value=event['category'], inline=True)
        embed.add_field(name="👤 Created by", value=event.get('created_by_name', 'Unknown'), inline=True)
        
        # RSVP summary
        yes_count = len(rsvps.get('yes', []))
        no_count = len(rsvps.get('no', []))
        maybe_count = len(rsvps.get('maybe', []))
        total_responses = yes_count + no_count + maybe_count
        
        summary = f"✅ **Attending:** {yes_count}\n❌ **Not Attending:** {no_count}\n🤔 **Maybe:** {maybe_count}\n📊 **Total Responses:** {total_responses}"
        embed.add_field(name="📈 RSVP Summary", value=summary, inline=True)
        
        # Attendance rate
        if total_responses > 0:
            attendance_rate = (yes_count / total_responses) * 100
            embed.add_field(name="🎯 Attendance Rate", value=f"{attendance_rate:.1f}%", inline=True)
        
        # Response timeline (last 10 responses)
        timeline = []
        all_responses = []
        for response_type in ['yes', 'no', 'maybe']:
            for rsvp in rsvps.get(response_type, []):
                all_responses.append(rsvp)
        
        all_responses.sort(key=lambda x: x.get('response_time', ''), reverse=True)
        
        for rsvp in all_responses[:10]:
            emoji = "✅" if rsvp['response'] == 'yes' else "❌" if rsvp['response'] == 'no' else "🤔"
            name = rsvp.get('discord_name', f"User {rsvp['user_id']}")
            timeline.append(f"{emoji} {name}")
        
        if timeline:
            embed.add_field(
                name="🕐 Recent Responses",
                value="\n".join(timeline),
                inline=True
            )
        
        embed.set_footer(text=f"Generated at")
        
        await interaction.followup.send(embed=embed)
    
    async def _generate_historical_report(self, interaction: discord.Interaction, days: int):
        """Generate historical attendance analysis"""
        # Get analytics
        analytics = await self.bot.db.get_event_analytics(interaction.guild.id, days)
        
        # Create report
        embed = discord.Embed(
            title=f"📈 Historical Attendance Analysis ({days} days)",
            description="Comprehensive event attendance patterns and trends",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        # Overview stats
        embed.add_field(name="📅 Total Events", value=str(analytics['total_events']), inline=True)
        embed.add_field(name="📬 Total Invitations", value=str(analytics['total_invitations']), inline=True)
        embed.add_field(name="📋 Total Responses", value=str(analytics['total_responses']), inline=True)
        
        # Response breakdown
        breakdown = analytics['response_breakdown']
        response_text = f"✅ Yes: {breakdown['yes']}\n❌ No: {breakdown['no']}\n🤔 Maybe: {breakdown['maybe']}"
        embed.add_field(name="Response Breakdown", value=response_text, inline=True)
        
        # Rates
        embed.add_field(name="📈 Response Rate", value=f"{analytics['response_rate']}%", inline=True)
        embed.add_field(name="🎯 Attendance Rate", value=f"{analytics['attendance_rate']}%", inline=True)
        
        # Category performance
        if analytics['category_stats']:
            cat_text = []
            for cat, stats in list(analytics['category_stats'].items())[:5]:
                attendance = 0
                if stats['total_responses'] > 0:
                    attendance = round(stats['yes_responses'] / stats['total_responses'] * 100, 1)
                cat_text.append(f"**{cat}**: {stats['count']} events ({attendance}% attendance)")
            
            embed.add_field(
                name="📋 Category Performance",
                value="\n".join(cat_text),
                inline=False
            )
        
        # Trends and insights
        insights = []
        if analytics['attendance_rate'] >= 70:
            insights.append("🎉 **Great engagement!** High attendance rates")
        elif analytics['attendance_rate'] >= 50:
            insights.append("👍 **Good engagement** with room for improvement")
        else:
            insights.append("⚠️ **Low attendance** - consider event timing/format")
        
        if analytics['response_rate'] >= 80:
            insights.append("📬 **Excellent response rates** - people are engaged")
        elif analytics['response_rate'] >= 60:
            insights.append("📊 **Good response rates** - most people are responding")
        else:
            insights.append("📢 **Low response rates** - consider follow-up reminders")
        
        if insights:
            embed.add_field(
                name="💡 Insights & Recommendations",
                value="\n".join(insights),
                inline=False
            )
        
        embed.set_footer(text="Historical data analysis")
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(EnhancedEventSystem(bot))
