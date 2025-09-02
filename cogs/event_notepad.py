import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import logging
import os
import sys
from typing import Optional, List, Dict

# Multiple approaches to ensure utils module can be imported
try:
    # First, try adding the project root to Python path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Also try current working directory
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    
    # Try /home/container if we're in that environment
    if '/home/container' not in sys.path:
        sys.path.insert(0, '/home/container')
        
except Exception:
    pass  # Continue even if path manipulation fails

from utils.permissions import has_required_permissions

logger = logging.getLogger(__name__)

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
        
        # Get RSVP data
        try:
            rsvps = await self.bot.db.get_event_rsvps(self.event['id'])
            invited_members = await self.bot.db.get_event_invitations(self.event['id'])
            
            # Create attendance tracking table
            attending = rsvps.get('yes', [])
            maybe_attending = rsvps.get('maybe', [])
            not_attending = rsvps.get('no', [])
            
            # Get list of invited member IDs who haven't responded
            responded_ids = set()
            for response_list in rsvps.values():
                responded_ids.update(member['user_id'] for member in response_list)
            
            no_response = []
            for invitation in invited_members:
                if invitation['user_id'] not in responded_ids:
                    # Get member info from guild
                    member = self.bot.get_guild(self.event['guild_id']).get_member(invitation['user_id']) if self.bot.get_guild(self.event['guild_id']) else None
                    if member:
                        no_response.append({
                            'user_id': invitation['user_id'],
                            'discord_name': member.display_name,
                            'rank': getattr(member, 'top_role', discord.Object(id=0)).name if hasattr(member, 'top_role') else 'Member'
                        })
            
            # Calculate totals
            total_invited = len(invited_members)
            total_responded = len(responded_ids)
            response_rate = (total_responded / total_invited * 100) if total_invited > 0 else 0
            
            # Summary statistics
            embed.add_field(
                name="📊 Summary Statistics",
                value=f"**Total Invited:** {total_invited}\\n"
                      f"**Total Responded:** {total_responded}\\n"
                      f"**Response Rate:** {response_rate:.1f}%\\n"
                      f"**Attending:** {len(attending)}\\n"
                      f"**Maybe:** {len(maybe_attending)}\\n"
                      f"**Not Attending:** {len(not_attending)}\\n"
                      f"**No Response:** {len(no_response)}",
                inline=True
            )
            
            # Attending members
            if attending:
                attending_list = []
                for member in attending[:15]:  # Limit to prevent overflow
                    rank = member.get('rank', 'Member')
                    name = member.get('discord_name', f"User {member['user_id']}")
                    attending_list.append(f"✅ **{rank}** - {name}")
                
                attending_text = "\\n".join(attending_list)
                if len(attending) > 15:
                    attending_text += f"\\n*...and {len(attending) - 15} more*"
                
                embed.add_field(
                    name=f"✅ Confirmed Attending ({len(attending)})",
                    value=attending_text,
                    inline=False
                )
            
            # Maybe attending
            if maybe_attending:
                maybe_list = []
                for member in maybe_attending[:10]:
                    rank = member.get('rank', 'Member')
                    name = member.get('discord_name', f"User {member['user_id']}")
                    maybe_list.append(f"❓ **{rank}** - {name}")
                
                maybe_text = "\\n".join(maybe_list)
                if len(maybe_attending) > 10:
                    maybe_text += f"\\n*...and {len(maybe_attending) - 10} more*"
                
                embed.add_field(
                    name=f"❓ Maybe Attending ({len(maybe_attending)})",
                    value=maybe_text,
                    inline=True
                )
            
            # Not attending
            if not_attending:
                not_list = []
                for member in not_attending[:10]:
                    rank = member.get('rank', 'Member')
                    name = member.get('discord_name', f"User {member['user_id']}")
                    not_list.append(f"❌ **{rank}** - {name}")
                
                not_text = "\\n".join(not_list)
                if len(not_attending) > 10:
                    not_text += f"\\n*...and {len(not_attending) - 10} more*"
                
                embed.add_field(
                    name=f"❌ Not Attending ({len(not_attending)})",
                    value=not_text,
                    inline=True
                )
            
            # No response (most important for tracking)
            if no_response:
                no_response_list = []
                for member in no_response[:15]:
                    rank = member.get('rank', 'Member')
                    name = member.get('discord_name', f"User {member['user_id']}")
                    no_response_list.append(f"⏳ **{rank}** - {name}")
                
                no_response_text = "\\n".join(no_response_list)
                if len(no_response) > 15:
                    no_response_text += f"\\n*...and {len(no_response) - 15} more*"
                
                embed.add_field(
                    name=f"⏳ Awaiting Response ({len(no_response)})",
                    value=no_response_text,
                    inline=False
                )
            
            # If no RSVPs at all
            if total_responded == 0:
                embed.add_field(
                    name="📝 RSVP Status",
                    value="No RSVP responses have been received yet.\\n"
                          "Invited members will appear in the 'Awaiting Response' section above.",
                    inline=False
                )
            
        except Exception as e:
            logger.error(f"Error getting RSVP data: {e}")
            embed.add_field(
                name="❌ Error",
                value="Unable to load RSVP data at this time.",
                inline=False
            )
        
        embed.set_footer(text=f"Event ID: {self.event['id']} | Use buttons below for actions")
        return embed
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.primary)
    async def refresh_rsvp(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the RSVP data"""
        embed = await self.create_rsvp_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="📊 Export Table", style=discord.ButtonStyle.secondary)
    async def export_table(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Export RSVP table as text file"""
        await interaction.response.defer()
        
        try:
            # Get RSVP data
            rsvps = await self.bot.db.get_event_rsvps(self.event['id'])
            invited_members = await self.bot.db.get_event_invitations(self.event['id'])
            
            # Generate report
            report_lines = []
            report_lines.append("=" * 60)
            report_lines.append(f"EVENT RSVP REPORT")
            report_lines.append("=" * 60)
            report_lines.append(f"Event: {self.event['event_name']}")
            
            if self.event.get('description'):
                report_lines.append(f"Description: {self.event['description']}")
            
            if self.event.get('event_date'):
                try:
                    if isinstance(self.event['event_date'], str):
                        event_date = datetime.fromisoformat(self.event['event_date'].replace('Z', '+00:00'))
                    else:
                        event_date = self.event['event_date']
                    report_lines.append(f"Date/Time: {event_date.strftime('%Y-%m-%d %H:%M:%S')}")
                except:
                    report_lines.append(f"Date/Time: {self.event['event_date']}")
            
            if self.event.get('location'):
                report_lines.append(f"Location: {self.event['location']}")
            
            report_lines.append("")
            
            # Summary
            attending = rsvps.get('yes', [])
            maybe = rsvps.get('maybe', [])
            not_attending = rsvps.get('no', [])
            
            responded_ids = set()
            for response_list in rsvps.values():
                responded_ids.update(member['user_id'] for member in response_list)
            
            total_invited = len(invited_members)
            total_responded = len(responded_ids)
            response_rate = (total_responded / total_invited * 100) if total_invited > 0 else 0
            
            report_lines.append("SUMMARY:")
            report_lines.append(f"Total Invited: {total_invited}")
            report_lines.append(f"Total Responded: {total_responded}")
            report_lines.append(f"Response Rate: {response_rate:.1f}%")
            report_lines.append(f"Attending: {len(attending)}")
            report_lines.append(f"Maybe: {len(maybe)}")
            report_lines.append(f"Not Attending: {len(not_attending)}")
            report_lines.append("")
            
            # Detailed lists
            if attending:
                report_lines.append("CONFIRMED ATTENDING:")
                report_lines.append("-" * 30)
                for member in attending:
                    rank = member.get('rank', 'Member')
                    name = member.get('discord_name', f"User {member['user_id']}")
                    report_lines.append(f"  {rank} - {name}")
                report_lines.append("")
            
            if maybe:
                report_lines.append("MAYBE ATTENDING:")
                report_lines.append("-" * 30)
                for member in maybe:
                    rank = member.get('rank', 'Member')
                    name = member.get('discord_name', f"User {member['user_id']}")
                    report_lines.append(f"  {rank} - {name}")
                report_lines.append("")
            
            if not_attending:
                report_lines.append("NOT ATTENDING:")
                report_lines.append("-" * 30)
                for member in not_attending:
                    rank = member.get('rank', 'Member')
                    name = member.get('discord_name', f"User {member['user_id']}")
                    report_lines.append(f"  {rank} - {name}")
                report_lines.append("")
            
            # No response
            no_response = []
            for invitation in invited_members:
                if invitation['user_id'] not in responded_ids:
                    member = self.bot.get_guild(self.event['guild_id']).get_member(invitation['user_id']) if self.bot.get_guild(self.event['guild_id']) else None
                    if member:
                        no_response.append({
                            'user_id': invitation['user_id'],
                            'discord_name': member.display_name,
                            'rank': getattr(member, 'top_role', discord.Object(id=0)).name if hasattr(member, 'top_role') else 'Member'
                        })
            
            if no_response:
                report_lines.append("AWAITING RESPONSE:")
                report_lines.append("-" * 30)
                for member in no_response:
                    rank = member.get('rank', 'Member')
                    name = member.get('discord_name', f"User {member['user_id']}")
                    report_lines.append(f"  {rank} - {name}")
                report_lines.append("")
            
            report_lines.append("=" * 60)
            report_lines.append(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            report_lines.append(f"Generated by: {interaction.user.display_name}")
            
            # Create file
            report_content = "\\n".join(report_lines)
            
            import io
            file_content = report_content.encode('utf-8')
            discord_file = discord.File(
                fp=io.BytesIO(file_content), 
                filename=f"event_rsvp_{self.event['event_name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
            )
            
            await interaction.followup.send(
                f"📊 **RSVP Table Exported**\\n\\nDetailed RSVP report for **{self.event['event_name']}** has been generated.",
                file=discord_file,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error exporting RSVP table: {e}")
            await interaction.followup.send(
                "❌ An error occurred while generating the report. Please try again.",
                ephemeral=True
            )
    
    @discord.ui.button(label="🔙 Back to Events", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_events(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to event list"""
        events = await self.bot.db.get_active_events(interaction.guild.id)
        view = EventNotepadView(self.bot, self.user_id, events)
        
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
        
        await interaction.response.edit_message(embed=embed, view=view)


class EventNotepad(commands.Cog):
    """Event notepad for tracking RSVP acceptance tables"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("EventNotepad cog initialized")

    @app_commands.command(name="event-notepad", description="Open the event notepad with RSVP acceptance tracking")
    async def event_notepad(self, interaction: discord.Interaction):
        """Open the event notepad dashboard"""
        if not await has_required_permissions(interaction, 
                                            allowed_roles=['Officer', 'Leadership', 'Admin', 'Moderator', 'Member']):
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
