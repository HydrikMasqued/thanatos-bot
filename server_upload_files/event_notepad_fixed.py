import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import logging
import os
import sys
from typing import Optional, List, Dict

# Add the current working directory to Python path as the very first thing
sys.path.insert(0, os.getcwd())
sys.path.insert(0, '/home/container')

logger = logging.getLogger(__name__)

# Try importing with error handling
try:
    from utils.permissions import has_required_permissions
    logger.info("✅ Successfully imported utils.permissions in event_notepad")
except ImportError as e:
    logger.error(f"❌ Failed to import utils.permissions: {e}")
    logger.error(f"Current working directory: {os.getcwd()}")
    logger.error(f"Python path: {sys.path[:5]}")
    
    # Create a dummy function to prevent the cog from completely failing
    async def has_required_permissions(*args, **kwargs):
        return True
    logger.warning("⚠️ Using dummy permissions function - all permissions will be allowed!")

class EventNotepadView(discord.ui.View):
    """View for event selection dropdown"""
    
    def __init__(self, bot, user_id: int, events: List[Dict]):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.events = events
        
        # Only add select menu if there are events
        if events:
            options = []
            for event in events[:25]:  # Discord limit
                event_name = event['event_name']
                
                # Add event date info
                date_str = "No date"
                if event.get('event_date'):
                    try:
                        if isinstance(event['event_date'], str):
                            event_date = datetime.fromisoformat(event['event_date'].replace('Z', '+00:00'))
                        else:
                            event_date = event['event_date']
                        date_str = event_date.strftime("%m/%d/%Y %I:%M %p")
                    except:
                        date_str = str(event['event_date'])[:16]
                
                # Get RSVP counts
                yes_count = event.get('yes_count', 0)
                total_rsvps = event.get('total_rsvps', 0)
                
                description = f"{date_str} | {yes_count}/{total_rsvps} attending"
                
                options.append(discord.SelectOption(
                    label=event_name[:100],  # Discord limit
                    description=description[:100],  # Discord limit
                    value=str(event['id']),
                    emoji='📅'
                ))
            
            select = discord.ui.Select(
                placeholder="Select an event to view RSVP table...",
                options=options,
                custom_id="event_select"
            )
            select.callback = self.event_select_callback
            self.add_item(select)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    async def event_select_callback(self, interaction: discord.Interaction):
        """Handle event selection"""
        event_id = int(interaction.data['values'][0])
        
        # Find the selected event
        selected_event = None
        for event in self.events:
            if event['id'] == event_id:
                selected_event = event
                break
        
        if not selected_event:
            await interaction.response.send_message("❌ Event not found.", ephemeral=True)
            return
        
        # Create the notepad view
        view = EventRSVPDetailView(self.bot, self.user_id, selected_event)
        embed = await view.create_rsvp_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.secondary)
    async def refresh_events(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the event list"""
        # Get updated events
        events = await self.bot.db.get_active_events(interaction.guild.id)
        
        # Create new view with updated events
        new_view = EventNotepadView(self.bot, self.user_id, events)
        
        embed = discord.Embed(
            title="📋 Event Notepad - RSVP Tracking",
            description=f"Select an event from the dropdown below to view detailed RSVP information.\\n\\n**Active events:** {len(events)}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if not events:
            embed.add_field(
                name="No Active Events",
                value="There are currently no active events to track.",
                inline=False
            )
        
        embed.set_footer(text="Use the dropdown to select an event for RSVP details")
        
        await interaction.response.edit_message(embed=embed, view=new_view)


class EventRSVPDetailView(discord.ui.View):
    """Detailed RSVP view for a specific event"""
    
    def __init__(self, bot, user_id: int, event: Dict):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.event = event
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    async def create_rsvp_embed(self) -> discord.Embed:
        """Create detailed RSVP embed with acceptance table"""
        event_name = self.event['event_name']
        
        embed = discord.Embed(
            title=f"📋 Event Notepad: {event_name}",
            description=f"**RSVP Tracking and Acceptance Table**",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        # Add event details
        if self.event.get('description'):
            embed.add_field(name="📝 Description", value=self.event['description'][:1024], inline=False)
        
        if self.event.get('event_date'):
            try:
                if isinstance(self.event['event_date'], str):
                    event_date = datetime.fromisoformat(self.event['event_date'].replace('Z', '+00:00'))
                else:
                    event_date = self.event['event_date']
                embed.add_field(name="📅 Date & Time", value=f"<t:{int(event_date.timestamp())}:F>", inline=True)
            except:
                embed.add_field(name="📅 Date & Time", value=str(self.event['event_date']), inline=True)
        
        if self.event.get('location'):
            embed.add_field(name="📍 Location", value=self.event['location'], inline=True)
        
        embed.set_footer(text=f"Event ID: {self.event['id']} | Use buttons below for actions")
        return embed
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.primary)
    async def refresh_rsvp(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the RSVP data"""
        embed = await self.create_rsvp_embed()
        await interaction.response.edit_message(embed=embed, view=self)


class EventNotepad(commands.Cog):
    """Event notepad for tracking RSVP acceptance tables"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("EventNotepad cog initialized")

    @app_commands.command(name="event-notepad", description="Open the event notepad with RSVP acceptance tracking")
    async def event_notepad(self, interaction: discord.Interaction):
        """Open the event notepad dashboard"""
        # Simplified permission check - just check if user has manage_guild or is in allowed roles
        user_permissions = interaction.user.guild_permissions
        allowed_roles = ['Officer', 'Leadership', 'Admin', 'Moderator', 'Member']
        user_roles = [role.name for role in interaction.user.roles]
        
        has_permission = (
            user_permissions.administrator or
            user_permissions.manage_guild or
            any(role in allowed_roles for role in user_roles)
        )
        
        if not has_permission:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        try:
            await interaction.response.defer()
            
            # Get active events
            events = await self.bot.db.get_active_events(interaction.guild.id)
            
            view = EventNotepadView(self.bot, interaction.user.id, events)
            
            embed = discord.Embed(
                title="📋 Event Notepad - RSVP Tracking",
                description=f"Select an event from the dropdown below to view detailed RSVP information.\\n\\n**Active events:** {len(events)}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            if not events:
                embed.add_field(
                    name="No Active Events",
                    value="There are currently no active events to track.\\nCreate an event with `/event-create` to get started.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="📊 What You Can Track:",
                    value="• Who has confirmed attendance\\n"
                          "• Who might attend (maybe responses)\\n"
                          "• Who is not attending\\n"
                          "• Who hasn't responded yet\\n"
                          "• Response rates and statistics\\n"
                          "• Export detailed reports",
                    inline=False
                )
            
            embed.set_footer(text="Use the dropdown to select an event for RSVP details")
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error opening event notepad: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while opening the event notepad: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(EventNotepad(bot))
