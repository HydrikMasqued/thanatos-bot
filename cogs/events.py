import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import json
from typing import Optional, List, Dict, Any
import logging
from utils.smart_time_formatter import SmartTimeFormatter
from utils.advanced_timestamp_parser import AdvancedTimestampParser

logger = logging.getLogger(__name__)

class EventDropdownView(discord.ui.View):
    """Dropdown view for selecting events"""
    
    def __init__(self, events: List[Dict], action: str, bot):
        super().__init__(timeout=300.0)
        self.events = events
        self.action = action
        self.bot = bot
        self.selected_event = None
        
        # Create dropdown
        options = []
        for event in events[:25]:  # Discord limit
            # Format date for display using smart formatter
            event_date = ""
            if event.get('event_date'):
                if isinstance(event['event_date'], str):
                    try:
                        dt = datetime.fromisoformat(event['event_date'].replace('Z', '+00:00'))
                        event_date = f" - {SmartTimeFormatter.format_discord_timestamp(dt, 'f')}"
                    except:
                        event_date = f" - {event['event_date']}"
                elif isinstance(event['event_date'], datetime):
                    event_date = f" - {SmartTimeFormatter.format_discord_timestamp(event['event_date'], 'f')}"
            
            options.append(discord.SelectOption(
                label=f"{event['event_name'][:50]}{event_date}"[:100],
                description=event.get('description', 'No description')[:100],
                value=str(event['id'])
            ))
        
        if options:
            self.event_select.options = options
        else:
            self.event_select.disabled = True
            self.event_select.placeholder = "No active events available"

    @discord.ui.select(placeholder="Choose an event...")
    async def event_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_event = int(select.values[0])
        
        # Get the event details
        selected_event_data = None
        for event in self.events:
            if event['id'] == self.selected_event:
                selected_event_data = event
                break
        
        if not selected_event_data:
            await interaction.response.send_message("❌ Selected event not found.", ephemeral=True)
            return
        
        if self.action == "invite":
            # Show invitation options
            view = InvitationTargetView(selected_event_data, self.bot)
            
            embed = discord.Embed(
                title="📮 Send Event Invitations",
                description=f"**Event:** {selected_event_data['event_name']}",
                color=0x00FF00
            )
            
            if selected_event_data.get('description'):
                embed.add_field(name="Description", value=selected_event_data['description'], inline=False)
            
            if selected_event_data.get('event_date'):
                event_timestamp = selected_event_data['event_date']
                if isinstance(event_timestamp, str):
                    try:
                        event_timestamp = datetime.fromisoformat(event_timestamp.replace('Z', '+00:00'))
                    except:
                        event_timestamp = None
                
                if event_timestamp:
                    embed.add_field(name="Date & Time", value=SmartTimeFormatter.format_event_datetime(event_timestamp), inline=False)
            
            embed.add_field(name="Next Step", value="Choose who to invite:", inline=False)
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        elif self.action == "view_rsvp":
            # Show RSVP table
            cog = self.bot.get_cog('EventSystem')
            if cog:
                await cog.show_event_rsvp_table(interaction, selected_event_data)
        
        elif self.action == "cancel":
            # Show cancel confirmation
            view = CancelConfirmationView(selected_event_data, self.bot)
            
            embed = discord.Embed(
                title="⚠️ Confirm Event Cancellation",
                description=f"Are you sure you want to cancel **{selected_event_data['event_name']}**?",
                color=0xFF4444
            )
            
            if selected_event_data.get('description'):
                embed.add_field(name="Description", value=selected_event_data['description'], inline=False)
            
            if selected_event_data.get('event_date'):
                event_timestamp = selected_event_data['event_date']
                if isinstance(event_timestamp, str):
                    try:
                        event_timestamp = datetime.fromisoformat(event_timestamp.replace('Z', '+00:00'))
                    except:
                        event_timestamp = None
                
                if event_timestamp:
                    embed.add_field(name="Date & Time", value=SmartTimeFormatter.format_event_datetime(event_timestamp), inline=False)
            
            embed.add_field(
                name="⚠️ This action will:",
                value="• Mark the event as cancelled\n• Stop all reminders\n• Notify all invited members\n• Cannot be undone",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=view)


class InvitationTargetView(discord.ui.View):
    """View for choosing invitation targets (users or roles)"""
    
    def __init__(self, event: Dict, bot):
        super().__init__(timeout=300.0)
        self.event = event
        self.bot = bot

    @discord.ui.button(label="Invite Individual Members", style=discord.ButtonStyle.primary, emoji="👤")
    async def invite_users(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            logger.info(f"Invite Individual Members button clicked by {interaction.user.display_name}")
            # Show user selection modal
            modal = UserSelectionModal(self.event, self.bot)
            logger.info(f"Created UserSelectionModal with title: {modal.title}")
            await interaction.response.send_modal(modal)
            logger.info("Modal sent successfully")
        except Exception as e:
            logger.error(f"Error in invite_users button: {e}")
            try:
                await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
            except:
                pass
    
    @discord.ui.button(label="Invite by Role", style=discord.ButtonStyle.secondary, emoji="👥")
    async def invite_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show role selection modal
        modal = RoleSelectionModal(self.event, self.bot)
        await interaction.response.send_modal(modal)


class UserSelectionModal(discord.ui.Modal):
    """Modal for selecting individual users to invite"""
    
    def __init__(self, event: Dict, bot):
        super().__init__(title=f"Invite Users to {event['event_name'][:30]}...")
        self.event = event
        self.bot = bot
        
        self.user_input = discord.ui.TextInput(
            label="Users to invite (names, IDs, @mentions)",
            placeholder="Jay, Thorikan, @user1, 123456789",
            style=discord.TextStyle.long,
            required=True,
            max_length=1000
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        cog = self.bot.get_cog('EventSystem')
        if not cog:
            await interaction.followup.send("❌ Event system not available.", ephemeral=True)
            return
        
        # Parse user input
        user_ids = await cog.parse_user_mentions(self.user_input.value, interaction.guild)
        
        if not user_ids:
            await interaction.followup.send("❌ No valid users found in your input.", ephemeral=True)
            return
        
        # Send invitations
        result = await cog.send_event_invitations(
            event=self.event,
            user_ids=user_ids,
            invited_by=interaction.user,
            guild=interaction.guild,
            method="individual"
        )
        
        message = f"✅ Sent invitations to {result['sent']} users."
        if result['failed'] > 0:
            message += f"\n❌ Failed to invite {result['failed']} users."
        
        await interaction.followup.send(message, ephemeral=True)


class RoleSelectionModal(discord.ui.Modal):
    """Modal for selecting role to invite"""
    
    def __init__(self, event: Dict, bot):
        super().__init__(title=f"Invite Role to {event['event_name'][:30]}...")
        self.event = event
        self.bot = bot
        
        self.role_input = discord.ui.TextInput(
            label="Role ID or @mention",
            placeholder="123456789 or @role_name",
            style=discord.TextStyle.short,
            required=True,
            max_length=100
        )
        self.add_item(self.role_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        cog = self.bot.get_cog('EventSystem')
        if not cog:
            await interaction.followup.send("❌ Event system not available.", ephemeral=True)
            return
        
        # Parse role
        role = await cog.parse_role_mention(self.role_input.value, interaction.guild)
        
        if not role:
            await interaction.followup.send("❌ Role not found.", ephemeral=True)
            return
        
        # Get all members with this role
        user_ids = [member.id for member in role.members]
        
        if not user_ids:
            await interaction.followup.send("❌ No members found with that role.", ephemeral=True)
            return
        
        # Send invitations
        result = await cog.send_event_invitations(
            event=self.event,
            user_ids=user_ids,
            invited_by=interaction.user,
            guild=interaction.guild,
            method="role",
            role_id=role.id
        )
        
        message = f"✅ Sent invitations to {result['sent']} members from role **{role.name}**."
        if result['failed'] > 0:
            message += f"\n❌ Failed to invite {result['failed']} users."
        
        await interaction.followup.send(message, ephemeral=True)


class CancelConfirmationView(discord.ui.View):
    """Confirmation view for cancelling events"""
    
    def __init__(self, event: Dict, bot):
        super().__init__(timeout=300.0)
        self.event = event
        self.bot = bot

    @discord.ui.button(label="Yes, Cancel Event", style=discord.ButtonStyle.danger, emoji="🚫")
    async def confirm_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        cog = self.bot.get_cog('EventSystem')
        if not cog:
            await interaction.followup.send("❌ Event system not available.", ephemeral=True)
            return
        
        # Cancel the event
        success = await cog.cancel_event_by_id(self.event['id'], interaction.user, interaction.guild)
        
        if success:
            embed = discord.Embed(
                title="✅ Event Cancelled",
                description=f"**{self.event['event_name']}** has been successfully cancelled.",
                color=0x00FF00,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="Actions Taken",
                value="• Event marked as cancelled\n• Reminders stopped\n• All invited members notified",
                inline=False
            )
            
            embed.set_footer(text=f"Cancelled by {interaction.user.display_name}")
            
            await interaction.edit_original_response(embed=embed, view=None)
        else:
            await interaction.followup.send(
                "❌ Failed to cancel the event. Please try again later.",
                ephemeral=True
            )
    
    @discord.ui.button(label="No, Keep Event", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="ℹ️ Event Cancellation Cancelled",
            description=f"**{self.event['event_name']}** will remain active.",
            color=0x0099FF
        )
        
        await interaction.response.edit_message(embed=embed, view=None)


class RSVPButton(discord.ui.View):
    """RSVP buttons for event DMs"""
    
    def __init__(self, event_id: int, user_id: int):
        super().__init__(timeout=None)  # Persistent view
        self.event_id = event_id
        self.user_id = user_id

    @discord.ui.button(emoji="✅", style=discord.ButtonStyle.success, custom_id="rsvp_yes")
    async def rsvp_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_rsvp(interaction, "yes")

    @discord.ui.button(emoji="❌", style=discord.ButtonStyle.danger, custom_id="rsvp_no")
    async def rsvp_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_rsvp(interaction, "no")

    @discord.ui.button(emoji="❓", style=discord.ButtonStyle.secondary, custom_id="rsvp_maybe")
    async def rsvp_maybe(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_rsvp(interaction, "maybe")
    
    async def handle_rsvp(self, interaction: discord.Interaction, response: str):
        """Handle RSVP response"""
        try:
            # Find the bot instance through the interaction client
            bot = interaction.client
            cog = bot.get_cog('EventSystem')
            
            if not cog:
                await interaction.response.send_message("❌ Event system not available.", ephemeral=True)
                return
            
            # Record the RSVP
            success = await cog.record_rsvp_response(
                event_id=self.event_id,
                user_id=self.user_id,
                response=response,
                interaction=interaction
            )
            
            if success:
                response_emojis = {"yes": "✅", "no": "❌", "maybe": "❓"}
                response_text = {"yes": "attending", "no": "not attending", "maybe": "might attend"}
                
                await interaction.response.send_message(
                    f"{response_emojis[response]} Thank you! You've RSVP'd as **{response_text[response]}** for this event.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Failed to record your RSVP. Please try again later.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error handling RSVP: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while processing your RSVP.",
                ephemeral=True
            )


class EventSystem(commands.Cog):
    """New integrated event system with DM invitations and RSVP tracking"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        
        # Add persistent views for RSVP buttons
        bot.add_view(RSVPButton(0, 0))  # Template view for persistence

    async def check_officer_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has officer permissions"""
        try:
            config = await self.db.get_server_config(interaction.guild.id)
            if not config or not config.get('officer_role_id'):
                await interaction.response.send_message(
                    "❌ Officer role not configured. Please contact a server administrator.",
                    ephemeral=True
                )
                return False
            
            officer_role = interaction.guild.get_role(config['officer_role_id'])
            if not officer_role:
                await interaction.response.send_message(
                    "❌ Officer role not found. Please contact a server administrator.",
                    ephemeral=True
                )
                return False
            
            if officer_role not in interaction.user.roles:
                await interaction.response.send_message(
                    "❌ You must have the officer role to use this command.",
                    ephemeral=True
                )
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking officer permissions: {e}")
            await interaction.response.send_message(
                "❌ Error checking permissions.",
                ephemeral=True
            )
            return False

    @app_commands.command(name="event-create", description="Create a new event")
    @app_commands.describe(
        name="Event name",
        description="Event description",
        date_time="Event date and time (e.g., 'tomorrow 8pm', 'friday 7:30pm', '2024-01-15 20:00')",
        location="Event location (optional)",
        max_attendees="Maximum number of attendees (optional)"
    )
    async def create_event(
        self, 
        interaction: discord.Interaction, 
        name: str, 
        description: str,
        date_time: str,
        location: Optional[str] = None,
        max_attendees: Optional[int] = None
    ):
        """Create a new event"""
        logger.info(f"Event-create command called by {interaction.user} (ID: {interaction.user.id}) in guild {interaction.guild.id}")
        if not await self.check_officer_permissions(interaction):
            return
        
        try:
            # Parse the date/time using advanced timestamp parser
            timestamp_result = AdvancedTimestampParser.parse_any_timestamp(date_time, context="event")
            
            if not timestamp_result or not timestamp_result['is_valid']:
                # Create a helpful error message with examples
                error_msg = f"❌ Could not parse date/time: '{date_time}'"
                if timestamp_result and timestamp_result.get('error'):
                    error_msg += f"\nError: {timestamp_result['error']}"
                
                error_msg += "\n\n📅 **Supported formats:**\n"
                error_msg += "• **Natural language:** 'tomorrow 8pm', 'next friday 7:30pm', 'january 15 at 8pm'\n"
                error_msg += "• **Relative time:** 'in 2 hours', '3 days from now', 'today in 4 hours'\n"
                error_msg += "• **Standard formats:** '2024-01-15 20:00', '1/15/2024 8:00 PM'\n"
                error_msg += "• **Discord timestamps:** '<t:1704670800:F>' (from Discord)\n"
                error_msg += "• **Event-specific:** 'starts at 8pm tomorrow', 'scheduled for friday'"
                
                await interaction.response.send_message(error_msg, ephemeral=True)
                return
            
            parsed_datetime = timestamp_result['datetime']
            
            # Validate the event time
            is_valid, error_message = SmartTimeFormatter.validate_event_time(parsed_datetime)
            if not is_valid:
                await interaction.response.send_message(f"❌ {error_message}", ephemeral=True)
                return
            
            # Ensure event is in the future
            if parsed_datetime <= datetime.now():
                await interaction.response.send_message(
                    "❌ Event date must be in the future.",
                    ephemeral=True
                )
                return
            
            # Create the event
            event_id = await self.db.create_event(
                guild_id=interaction.guild.id,
                event_name=name,
                description=description,
                category="General",  # Default category
                event_date=parsed_datetime,
                location=location,
                max_attendees=max_attendees,
                created_by_id=interaction.user.id
            )
            
            # Add event to precise reminder system
            if hasattr(self.bot, 'precise_reminders'):
                event_data = {
                    'id': event_id,
                    'guild_id': interaction.guild.id,
                    'event_name': name,
                    'event_date': parsed_datetime,
                    'reminder_hours_before': 24,  # Default 24 hours
                    'created_by_id': interaction.user.id,
                    'description': description,
                    'location': location
                }
                await self.bot.precise_reminders.add_event_reminder(event_data)
            
            embed = discord.Embed(
                title="✅ Event Created Successfully",
                description=f"**{name}** has been created!",
                color=0x00FF00,
                timestamp=datetime.now()
            )
            
            embed.add_field(name="📝 Description", value=description, inline=False)
            
            # Show multiple timestamp formats for user convenience
            timestamp_formats = AdvancedTimestampParser.suggest_timestamp_formats(parsed_datetime)
            date_time_value = f"{timestamp_formats['full_long']} ({timestamp_formats['relative']})"
            
            # Add parsing information if available
            if timestamp_result.get('source_format') and timestamp_result.get('confidence'):
                confidence_emoji = "🎯" if timestamp_result['confidence'] >= 0.9 else "✅" if timestamp_result['confidence'] >= 0.7 else "⚠️"
                date_time_value += f"\n{confidence_emoji} *Parsed from: {timestamp_result['source_format']} (confidence: {timestamp_result['confidence']:.0%})*"
            
            embed.add_field(
                name="📅 Date & Time", 
                value=date_time_value, 
                inline=False
            )
            
            if location:
                embed.add_field(name="📍 Location", value=location, inline=True)
            
            if max_attendees:
                embed.add_field(name="👥 Max Attendees", value=str(max_attendees), inline=True)
            
            embed.add_field(name="🆔 Event ID", value=str(event_id), inline=True)
            embed.set_footer(text=f"Created by {interaction.user.display_name}")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while creating the event.",
                ephemeral=True
            )

    @app_commands.command(name="event-list", description="List all active events")
    async def list_events(self, interaction: discord.Interaction):
        """List all active events"""
        if not await self.check_officer_permissions(interaction):
            return
        
        try:
            events = await self.db.get_active_events(interaction.guild.id)
            
            if not events:
                embed = discord.Embed(
                    title="📅 No Active Events",
                    description="There are currently no active events.",
                    color=0x808080
                )
                await interaction.response.send_message(embed=embed)
                return
            
            embed = discord.Embed(
                title="📅 Active Events",
                color=0x0099FF,
                timestamp=datetime.now()
            )
            
            for event in events[:10]:  # Limit to 10 events for embed space
                event_time = ""
                if event.get('event_date'):
                    # Handle both datetime objects and string dates
                    event_datetime = event['event_date']
                    if isinstance(event_datetime, str):
                        try:
                            event_datetime = datetime.fromisoformat(event_datetime.replace('Z', '+00:00'))
                        except ValueError:
                            event_time = f"**When:** {event_datetime}"  # Fallback to string display
                    
                    if isinstance(event_datetime, datetime):
                        event_time = f"<t:{int(event_datetime.timestamp())}:F>\n<t:{int(event_datetime.timestamp())}:R>"
                
                field_value = f"**Description:** {event.get('description', 'No description')}\n"
                if event_time:
                    field_value += f"**When:** {event_time}\n"
                if event.get('location'):
                    field_value += f"**Location:** {event['location']}\n"
                
                # Add RSVP counts
                yes_count = event.get('yes_count', 0)
                no_count = event.get('no_count', 0) 
                maybe_count = event.get('maybe_count', 0)
                
                field_value += f"**RSVPs:** ✅ {yes_count} | ❌ {no_count} | ❓ {maybe_count}"
                
                embed.add_field(
                    name=f"🎉 {event['event_name']} (ID: {event['id']})",
                    value=field_value,
                    inline=False
                )
            
            if len(events) > 10:
                embed.set_footer(text=f"Showing 10 of {len(events)} active events")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing events: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while retrieving events.",
                ephemeral=True
            )

    @app_commands.command(name="event-invite", description="Send invitations for an event")
    async def invite_to_event(self, interaction: discord.Interaction):
        """Send invitations to an event via dropdown selection"""
        if not await self.check_officer_permissions(interaction):
            return
        
        try:
            # Get active events
            events = await self.db.get_active_events(interaction.guild.id)
            
            if not events:
                await interaction.response.send_message(
                    "❌ No active events found. Create an event first using `/event-create`.",
                    ephemeral=True
                )
                return
            
            # Show event selection dropdown
            view = EventDropdownView(events, "invite", self.bot)
            
            embed = discord.Embed(
                title="📮 Send Event Invitations",
                description="Select an event to send invitations for:",
                color=0x00FF00
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in invite command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while preparing invitations.",
                ephemeral=True
            )


    @app_commands.command(name="event-cancel", description="Cancel an active event")
    async def cancel_event(self, interaction: discord.Interaction):
        """Cancel an event via dropdown selection"""
        if not await self.check_officer_permissions(interaction):
            return
        
        try:
            # Get active events
            events = await self.db.get_active_events(interaction.guild.id)
            
            if not events:
                await interaction.response.send_message(
                    "❌ No active events found to cancel.",
                    ephemeral=True
                )
                return
            
            # Show event selection dropdown
            view = EventDropdownView(events, "cancel", self.bot)
            
            embed = discord.Embed(
                title="🚫 Cancel Event",
                description="Select an event to cancel:",
                color=0xFF4444
            )
            
            embed.add_field(
                name="⚠️ Warning",
                value="Cancelling an event will:\n• Mark it as inactive\n• Stop sending reminders\n• Notify all invited members",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in cancel event command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while preparing event cancellation.",
                ephemeral=True
            )

    async def parse_user_mentions(self, input_text: str, guild: discord.Guild) -> List[int]:
        """Parse user mentions, IDs, display names, and usernames from input text"""
        user_ids = []
        
        # Split by spaces and commas
        parts = input_text.replace(',', ' ').split()
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            found_user = None
            
            try:
                # Method 1: Try to extract user ID from mention format
                if part.startswith('<@') and part.endswith('>'):
                    # Remove <@ and >
                    id_part = part[2:-1]
                    # Remove ! if present (for nickname mentions)
                    if id_part.startswith('!'):
                        id_part = id_part[1:]
                    user_id = int(id_part)
                    found_user = guild.get_member(user_id)
                
                # Method 2: Try to parse as direct ID
                elif part.isdigit():
                    user_id = int(part)
                    found_user = guild.get_member(user_id)
                
            except ValueError:
                pass
            
            # Method 3: If not found by ID/mention, try to find by display name or username
            if not found_user:
                # Search by display name (case-insensitive)
                for member in guild.members:
                    if member.display_name.lower() == part.lower():
                        found_user = member
                        break
                
                # If still not found, search by username (without discriminator)
                if not found_user:
                    for member in guild.members:
                        # Handle both old format (username#1234) and new format (@username)
                        if hasattr(member, 'name'):  # New username format
                            if member.name.lower() == part.lower():
                                found_user = member
                                break
                        
                        # Also check global_name (display name) again with more flexible matching
                        if hasattr(member, 'global_name') and member.global_name:
                            if member.global_name.lower() == part.lower():
                                found_user = member
                                break
                
                # If still not found, try partial matching for display names
                if not found_user:
                    for member in guild.members:
                        if part.lower() in member.display_name.lower():
                            found_user = member
                            break
            
            # Add user if found
            if found_user:
                user_ids.append(found_user.id)
        
        return list(set(user_ids))  # Remove duplicates

    async def parse_role_mention(self, input_text: str, guild: discord.Guild) -> Optional[discord.Role]:
        """Parse role mention or ID from input text"""
        input_text = input_text.strip()
        
        try:
            # Try to extract role ID from mention format
            if input_text.startswith('<@&') and input_text.endswith('>'):
                role_id = int(input_text[3:-1])
            else:
                # Try to parse as direct ID
                role_id = int(input_text)
            
            return guild.get_role(role_id)
            
        except ValueError:
            return None

    async def send_event_invitations(self, event: Dict, user_ids: List[int], invited_by: discord.Member, guild: discord.Guild, method: str, role_id: Optional[int] = None) -> Dict[str, int]:
        """Send event invitations to users"""
        sent = 0
        failed = 0
        
        for user_id in user_ids:
            try:
                member = guild.get_member(user_id)
                if not member:
                    failed += 1
                    continue
                
                # Record invitation in database
                invite_success = await self.db.invite_user_to_event(
                    event_id=event['id'],
                    guild_id=guild.id,
                    user_id=user_id,
                    invited_by_id=invited_by.id,
                    invitation_method=method,
                    role_id=role_id
                )
                
                if not invite_success:
                    # User already invited
                    continue
                
                # Send DM with RSVP buttons
                dm_success = await self.send_event_dm(event, member)
                
                if dm_success:
                    sent += 1
                    
                    # Send notification to officers
                    await self.notify_officers_invitation_sent(guild, event, member, invited_by)
                else:
                    failed += 1
                    
            except Exception as e:
                logger.error(f"Error sending invitation to {user_id}: {e}")
                failed += 1
        
        return {"sent": sent, "failed": failed}

    async def send_event_dm(self, event: Dict, member: discord.Member) -> bool:
        """Send event invitation DM to a member"""
        try:
            embed = discord.Embed(
                title="🎉 Event Invitation",
                description=f"You're invited to **{event['event_name']}**!",
                color=0x00FF00
            )
            
            # Add event details
            embed.add_field(name="📝 Description", value=event.get('description', 'No description provided'), inline=False)
            
            if event.get('event_date'):
                embed.add_field(
                    name="📅 Date & Time", 
                    value=f"<t:{int(event['event_date'].timestamp())}:F>\n<t:{int(event['event_date'].timestamp())}:R>", 
                    inline=False
                )
            
            if event.get('location'):
                embed.add_field(name="📍 Location", value=event['location'], inline=False)
            
            if event.get('max_attendees'):
                embed.add_field(name="👥 Max Attendees", value=str(event['max_attendees']), inline=True)
            
            embed.add_field(name="🤔 Will you attend?", value="Click one of the buttons below to RSVP:", inline=False)
            
            embed.set_footer(text=f"Event ID: {event['id']}")
            
            # Create RSVP buttons
            view = RSVPButton(event['id'], member.id)
            
            await member.send(embed=embed, view=view)
            
            # Mark DM as sent
            await self.db.mark_dm_sent(event['id'], member.id)
            
            return True
            
        except discord.Forbidden:
            logger.warning(f"Cannot send DM to {member.display_name} ({member.id}) - DMs disabled")
            return False
        except Exception as e:
            logger.error(f"Error sending event DM to {member.id}: {e}")
            return False

    async def notify_officers_invitation_sent(self, guild: discord.Guild, event: Dict, invitee: discord.Member, invited_by: discord.Member):
        """Notify officers that an invitation was sent"""
        try:
            config = await self.db.get_server_config(guild.id)
            if not config:
                return
            
            # Send to notification channel
            if config.get('notification_channel_id'):
                channel = guild.get_channel(config['notification_channel_id'])
                if channel:
                    embed = discord.Embed(
                        title="📮 Event Invitation Sent",
                        description=f"**{invitee.display_name}** was invited to **{event['event_name']}**",
                        color=0x0099FF,
                        timestamp=datetime.now()
                    )
                    
                    embed.add_field(name="Invited by", value=invited_by.mention, inline=True)
                    embed.add_field(name="Event ID", value=str(event['id']), inline=True)
                    
                    await channel.send(embed=embed)
                    
        except Exception as e:
            logger.error(f"Error sending officer notification: {e}")

    async def record_rsvp_response(self, event_id: int, user_id: int, response: str, interaction: discord.Interaction) -> bool:
        """Record RSVP response and notify officers"""
        try:
            # Record the RSVP
            success = await self.db.record_rsvp(
                event_id=event_id,
                guild_id=interaction.guild.id if interaction.guild else 0,
                user_id=user_id,
                response=response
            )
            
            if success and interaction.guild:
                # Get event details
                event = await self.db.get_event_by_id(event_id)
                if event:
                    # Notify officers of the response
                    await self.notify_officers_rsvp_response(interaction.guild, event, interaction.user, response)
            
            return success
            
        except Exception as e:
            logger.error(f"Error recording RSVP response: {e}")
            return False

    async def notify_officers_rsvp_response(self, guild: discord.Guild, event: Dict, responder: discord.Member, response: str):
        """Notify officers of an RSVP response"""
        try:
            config = await self.db.get_server_config(guild.id)
            if not config or not config.get('notification_channel_id'):
                return
            
            channel = guild.get_channel(config['notification_channel_id'])
            if not channel:
                return
            
            response_emojis = {"yes": "✅", "no": "❌", "maybe": "❓"}
            response_colors = {"yes": 0x00FF00, "no": 0xFF0000, "maybe": 0xFFFF00}
            response_text = {"yes": "attending", "no": "not attending", "maybe": "might attend"}
            
            embed = discord.Embed(
                title="📝 RSVP Response Received",
                description=f"{response_emojis[response]} **{responder.display_name}** is **{response_text[response]}** {event['event_name']}",
                color=response_colors[response],
                timestamp=datetime.now()
            )
            
            embed.add_field(name="Event", value=event['event_name'], inline=True)
            embed.add_field(name="Member", value=responder.mention, inline=True)
            embed.add_field(name="Response", value=f"{response_emojis[response]} {response_text[response].title()}", inline=True)
            
            await channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error sending RSVP notification: {e}")

    async def cancel_event_by_id(self, event_id: int, cancelled_by: discord.Member, guild: discord.Guild) -> bool:
        """Cancel an event and notify all invited members"""
        try:
            # Remove event from precise reminder system
            if hasattr(self.bot, 'precise_reminders'):
                await self.bot.precise_reminders.remove_event_reminder(event_id)
            
            # Mark event as cancelled in database
            success = await self.db.cancel_event(event_id)
            if not success:
                logger.error(f"Failed to cancel event {event_id} in database")
                return False
            
            # Get event details for notifications
            event = await self.db.get_event_by_id(event_id)
            if not event:
                logger.error(f"Event {event_id} not found after cancellation")
                return False
            
            # Get all invited members
            invited_members = await self.db.get_event_invited_members(event_id)
            
            # Send cancellation notifications
            notification_count = 0
            for member_id in invited_members:
                member = guild.get_member(member_id)
                if member:
                    dm_sent = await self.send_cancellation_dm(event, member, cancelled_by)
                    if dm_sent:
                        notification_count += 1
            
            # Notify officers
            await self.notify_officers_event_cancelled(guild, event, cancelled_by, notification_count)
            
            logger.info(f"Event {event_id} cancelled successfully. Notified {notification_count} members.")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling event {event_id}: {e}")
            return False
    
    async def send_cancellation_dm(self, event: Dict, member: discord.Member, cancelled_by: discord.Member) -> bool:
        """Send cancellation notification DM to a member"""
        try:
            embed = discord.Embed(
                title="🚫 Event Cancelled",
                description=f"**{event['event_name']}** has been cancelled.",
                color=0xFF4444,
                timestamp=datetime.now()
            )
            
            embed.add_field(name="📝 Event", value=event['event_name'], inline=False)
            
            if event.get('description'):
                embed.add_field(name="Description", value=event['description'], inline=False)
            
            if event.get('event_date'):
                embed.add_field(
                    name="📅 Originally Scheduled",
                    value=f"<t:{int(event['event_date'].timestamp())}:F>",
                    inline=False
                )
            
            embed.add_field(
                name="Cancelled by",
                value=cancelled_by.display_name,
                inline=True
            )
            
            embed.set_footer(text="We apologize for any inconvenience.")
            
            await member.send(embed=embed)
            return True
            
        except discord.Forbidden:
            logger.warning(f"Cannot send cancellation DM to {member.display_name} ({member.id}) - DMs disabled")
            return False
        except Exception as e:
            logger.error(f"Error sending cancellation DM to {member.id}: {e}")
            return False
    
    async def notify_officers_event_cancelled(self, guild: discord.Guild, event: Dict, cancelled_by: discord.Member, notification_count: int):
        """Notify officers that an event was cancelled"""
        try:
            config = await self.db.get_server_config(guild.id)
            if not config or not config.get('notification_channel_id'):
                return
            
            channel = guild.get_channel(config['notification_channel_id'])
            if not channel:
                return
            
            embed = discord.Embed(
                title="🚫 Event Cancelled",
                description=f"**{event['event_name']}** has been cancelled",
                color=0xFF4444,
                timestamp=datetime.now()
            )
            
            embed.add_field(name="Event", value=event['event_name'], inline=True)
            embed.add_field(name="Cancelled by", value=cancelled_by.mention, inline=True)
            embed.add_field(name="Event ID", value=str(event['id']), inline=True)
            
            if event.get('event_date'):
                embed.add_field(
                    name="📅 Originally Scheduled",
                    value=f"<t:{int(event['event_date'].timestamp())}:F>",
                    inline=False
                )
            
            embed.add_field(
                name="📊 Notifications Sent",
                value=f"Successfully notified {notification_count} invited members",
                inline=False
            )
            
            await channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error sending event cancellation notification: {e}")

    async def show_event_rsvp_table(self, interaction: discord.Interaction, event: Dict):
        """Show RSVP table for an event"""
        try:
            # Get all RSVPs for the event
            rsvps = await self.db.get_event_rsvps(event['id'])
            
            embed = discord.Embed(
                title=f"📊 RSVP Responses - {event['event_name']}",
                color=0x0099FF,
                timestamp=datetime.now()
            )
            
            # Add event info
            if event.get('event_date'):
                embed.add_field(
                    name="📅 Event Date",
                    value=f"<t:{int(event['event_date'].timestamp())}:F>",
                    inline=False
                )
            
            # Count responses
            total_responses = sum(len(rsvps[response]) for response in rsvps)
            
            if total_responses == 0:
                embed.description = "No RSVP responses yet."
                await interaction.response.edit_message(embed=embed, view=None)
                return
            
            # Add response sections
            response_sections = {
                "yes": ("✅ Attending", 0x00FF00),
                "maybe": ("❓ Maybe Attending", 0xFFFF00), 
                "no": ("❌ Not Attending", 0xFF0000)
            }
            
            for response_type, (title, color) in response_sections.items():
                members = rsvps.get(response_type, [])
                if members:
                    # Format member list with ranks
                    member_list = []
                    for member in members[:15]:  # Limit to prevent embed overflow
                        rank = member.get('rank', 'Member')
                        name = member.get('discord_name', f"User {member['user_id']}")
                        member_list.append(f"**{rank}** - {name}")
                    
                    member_text = "\n".join(member_list)
                    if len(members) > 15:
                        member_text += f"\n*... and {len(members) - 15} more*"
                    
                    embed.add_field(
                        name=f"{title} ({len(members)})",
                        value=member_text or "None",
                        inline=False
                    )
            
            # Add summary
            embed.add_field(
                name="📈 Summary",
                value=(
                    f"**Total Responses:** {total_responses}\n"
                    f"✅ **Attending:** {len(rsvps.get('yes', []))}\n"
                    f"❓ **Maybe:** {len(rsvps.get('maybe', []))}\n"
                    f"❌ **Not Attending:** {len(rsvps.get('no', []))}"
                ),
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            logger.error(f"Error showing RSVP table: {e}")
            await interaction.response.edit_message(
                content="❌ An error occurred while retrieving RSVP data.",
                embed=None,
                view=None
            )

    @app_commands.command(name="event-finish", description="Manually finish an event and record attendance")
    @app_commands.describe(
        event_id="Event ID to finish",
        attendees="User IDs or @mentions of attendees (space/comma separated)"
    )
    async def finish_event_manual(self, interaction: discord.Interaction, event_id: int, attendees: str):
        """Manually finish an event and record attendance"""
        if not await self.check_officer_permissions(interaction):
            return
        
        await interaction.response.defer()
        
        try:
            # Get event details
            event = await self.db.get_event_by_id(event_id)
            if not event:
                await interaction.followup.send("❌ Event not found.", ephemeral=True)
                return
            
            if event['guild_id'] != interaction.guild.id:
                await interaction.followup.send("❌ Event not found in this server.", ephemeral=True)
                return
            
            if not event.get('is_active', True):
                await interaction.followup.send("❌ Event is not active (already finished/cancelled).", ephemeral=True)
                return
            
            # Parse attendee mentions/IDs
            attendee_ids = await self.parse_user_mentions(attendees, interaction.guild)
            
            if not attendee_ids:
                await interaction.followup.send("❌ No valid attendees found in your input.", ephemeral=True)
                return
            
            # Get list of invited members
            invited_members = await self.db.get_event_invited_members(event_id)
            
            # Record attendance for attendees (present)
            attendance_recorded = 0
            for user_id in attendee_ids:
                if user_id in invited_members:
                    success = await self.db.record_attendance(
                        event_id=event_id,
                        guild_id=interaction.guild.id,
                        user_id=user_id,
                        attendance_status='present',
                        arrival_time=datetime.now(),
                        notes="Manually recorded attendance",
                        recorded_by_id=interaction.user.id
                    )
                    if success:
                        attendance_recorded += 1
            
            # Record absent status for invited members who weren't marked present
            absent_recorded = 0
            for user_id in invited_members:
                if user_id not in attendee_ids:
                    success = await self.db.record_attendance(
                        event_id=event_id,
                        guild_id=interaction.guild.id,
                        user_id=user_id,
                        attendance_status='absent',
                        notes="Marked absent (not in attendance list)",
                        recorded_by_id=interaction.user.id
                    )
                    if success:
                        absent_recorded += 1
            
            # Finish the event
            success = await self.db.finish_event(event_id)
            
            if not success:
                await interaction.followup.send("❌ Failed to finish the event.", ephemeral=True)
                return
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Event Finished Successfully",
                description=f"**{event['event_name']}** has been finished and attendance recorded.",
                color=0x00FF00,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📊 Attendance Summary",
                value=(
                    f"✅ **Present:** {attendance_recorded}\n"
                    f"❌ **Absent:** {absent_recorded}\n"
                    f"📋 **Total Invited:** {len(invited_members)}"
                ),
                inline=False
            )
            
            embed.add_field(
                name="📅 Event Details",
                value=(
                    f"**Event:** {event['event_name']}\n"
                    f"**ID:** {event_id}\n"
                    f"**Finished by:** {interaction.user.display_name}"
                ),
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error finishing event manually: {e}")
            await interaction.followup.send(
                "❌ An error occurred while finishing the event.",
                ephemeral=True
            )
    
    @app_commands.command(name="event-attendance", description="View attendance records for an event")
    @app_commands.describe(event_id="Event ID to view attendance for")
    async def view_event_attendance(self, interaction: discord.Interaction, event_id: int):
        """View attendance records for an event"""
        if not await self.check_officer_permissions(interaction):
            return
        
        try:
            # Get event details
            event = await self.db.get_event_by_id(event_id)
            if not event:
                await interaction.response.send_message("❌ Event not found.", ephemeral=True)
                return
            
            if event['guild_id'] != interaction.guild.id:
                await interaction.response.send_message("❌ Event not found in this server.", ephemeral=True)
                return
            
            # Get attendance records
            attendance_records = await self.db.get_event_attendance(event_id)
            
            embed = discord.Embed(
                title=f"📊 Event Attendance - {event['event_name']}",
                color=0x0099FF,
                timestamp=datetime.now()
            )
            
            # Add event info
            if event.get('event_date'):
                embed.add_field(
                    name="📅 Event Date",
                    value=f"<t:{int(event['event_date'].timestamp())}:F>",
                    inline=False
                )
            
            if not attendance_records:
                embed.description = "No attendance records found for this event."
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Group by attendance status
            attendance_groups = {"present": [], "late": [], "absent": []}
            for record in attendance_records:
                status = record.get('attendance_status', 'absent')
                if status in attendance_groups:
                    attendance_groups[status].append(record)
            
            # Add sections for each status
            status_info = {
                "present": ("✅ Present", 0x00FF00),
                "late": ("🟡 Late", 0xFFFF00),
                "absent": ("❌ Absent", 0xFF0000)
            }
            
            for status, (title, color) in status_info.items():
                records = attendance_groups.get(status, [])
                if records:
                    member_list = []
                    for record in records[:15]:  # Limit to prevent overflow
                        rank = record.get('rank', 'Member')
                        name = record.get('discord_name', f"User {record['user_id']}")
                        
                        # Add arrival time for present/late members
                        time_info = ""
                        if status in ['present', 'late'] and record.get('arrival_time'):
                            try:
                                arrival_dt = datetime.fromisoformat(record['arrival_time'].replace('Z', '+00:00'))
                                time_info = f" (arrived <t:{int(arrival_dt.timestamp())}:t>)"
                            except:
                                pass
                        
                        member_list.append(f"**{rank}** - {name}{time_info}")
                    
                    member_text = "\n".join(member_list)
                    if len(records) > 15:
                        member_text += f"\n*... and {len(records) - 15} more*"
                    
                    embed.add_field(
                        name=f"{title} ({len(records)})",
                        value=member_text,
                        inline=False
                    )
            
            # Add summary
            total_present = len(attendance_groups['present'])
            total_late = len(attendance_groups['late'])
            total_absent = len(attendance_groups['absent'])
            total_records = total_present + total_late + total_absent
            
            embed.add_field(
                name="📈 Summary",
                value=(
                    f"**Total Records:** {total_records}\n"
                    f"✅ **Present:** {total_present}\n"
                    f"🟡 **Late:** {total_late}\n"
                    f"❌ **Absent:** {total_absent}\n"
                    f"📊 **Attendance Rate:** {((total_present + total_late) / total_records * 100):.1f}%" if total_records > 0 else "No records"
                ),
                inline=False
            )
            
            embed.add_field(
                name="ℹ️ Event Status",
                value="🔴 **Finished**" if not event.get('is_active', True) else "🟢 **Active**",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error viewing event attendance: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while retrieving attendance data.",
                ephemeral=True
            )
    
    @app_commands.command(name="member-attendance", description="View attendance history for a member")
    @app_commands.describe(
        member="Member to view attendance history for",
        limit="Number of recent events to show (default: 10)"
    )
    async def view_member_attendance(self, interaction: discord.Interaction, member: discord.Member, limit: int = 10):
        """View attendance history for a member"""
        if not await self.check_officer_permissions(interaction):
            return
        
        try:
            # Validate limit
            if limit < 1 or limit > 50:
                await interaction.response.send_message("❌ Limit must be between 1 and 50.", ephemeral=True)
                return
            
            # Get attendance history
            attendance_history = await self.db.get_member_attendance_history(
                interaction.guild.id, member.id, limit
            )
            
            embed = discord.Embed(
                title=f"📊 Attendance History - {member.display_name}",
                color=0x0099FF,
                timestamp=datetime.now()
            )
            
            if not attendance_history:
                embed.description = f"{member.display_name} has no recorded event attendance."
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Add attendance records
            for i, record in enumerate(attendance_history):
                status_emoji = {
                    'present': '✅',
                    'late': '🟡', 
                    'absent': '❌'
                }.get(record.get('attendance_status', 'absent'), '❓')
                
                event_date = ""
                if record.get('event_date'):
                    try:
                        event_dt = record['event_date']
                        if isinstance(event_dt, str):
                            event_dt = datetime.fromisoformat(event_dt.replace('Z', '+00:00'))
                        event_date = f"<t:{int(event_dt.timestamp())}:d>"
                    except:
                        event_date = str(record['event_date'])[:10]
                
                field_value = f"**Status:** {status_emoji} {record.get('attendance_status', 'Unknown').title()}\n"
                field_value += f"**Date:** {event_date}\n"
                if record.get('category'):
                    field_value += f"**Category:** {record['category']}\n"
                if record.get('arrival_time') and record.get('attendance_status') in ['present', 'late']:
                    try:
                        arrival_dt = datetime.fromisoformat(record['arrival_time'].replace('Z', '+00:00'))
                        field_value += f"**Arrival:** <t:{int(arrival_dt.timestamp())}:t>\n"
                    except:
                        pass
                
                embed.add_field(
                    name=f"{i+1}. {record.get('event_name', 'Unknown Event')}",
                    value=field_value,
                    inline=True if i % 2 == 0 else False
                )
            
            # Add summary statistics
            present_count = sum(1 for r in attendance_history if r.get('attendance_status') == 'present')
            late_count = sum(1 for r in attendance_history if r.get('attendance_status') == 'late')
            absent_count = sum(1 for r in attendance_history if r.get('attendance_status') == 'absent')
            total_events = len(attendance_history)
            
            attendance_rate = ((present_count + late_count) / total_events * 100) if total_events > 0 else 0
            
            embed.add_field(
                name="📈 Summary Statistics",
                value=(
                    f"**Events:** {total_events}\n"
                    f"✅ **Present:** {present_count}\n"
                    f"🟡 **Late:** {late_count}\n"
                    f"❌ **Absent:** {absent_count}\n"
                    f"📊 **Attendance Rate:** {attendance_rate:.1f}%"
                ),
                inline=False
            )
            
            if total_events >= limit:
                embed.set_footer(text=f"Showing {limit} most recent events")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error viewing member attendance: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while retrieving attendance data.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(EventSystem(bot))
